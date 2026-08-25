"""
Demo for the ALPHA_TESTERS.md "More Prompt doesn't trigger when output is
split across separate send() calls" entry.

Not wired into the real server -- a standalone, simplified stand-in for
GameContext.send()/_wants_pagination() (server/network_context.py) so the
buffering idea can be seen running without touching the real async/PETSCII
machinery. Run directly: `python3 experiments/more_prompt_buffering_demo.py`

Shows two versions of the same scenario -- a command that calls send() twice
(20 lines, then 20 more), against a player with a 24-row screen (page_size
23) and More Prompt on:

  1. NaiveContext -- today's behavior: each send() call decides pagination
     against only its own lines. 20 <= 23 both times, so neither call
     paginates, even though the two calls together are 40 lines.

  2. BufferedContext -- the proposed fix: send() appends to a per-turn
     buffer instead of deciding immediately; flush_turn() (called once at
     the natural end of a turn, e.g. before the next ctx.prompt()) makes
     the pagination decision against the COMBINED total.
"""

from dataclasses import dataclass, field


PAGE_SIZE = 23  # matches network_context.py's page_size = screen_rows - 1


@dataclass
class NaiveContext:
    """Stand-in for today's GameContext.send()/_wants_pagination()."""
    more_prompt_on: bool = True
    sent_pages: list[list[str]] = field(default_factory=list)  # what actually went out, one send() = one page

    def send(self, lines: list[str]) -> None:
        wants_pagination = len(lines) > PAGE_SIZE and self.more_prompt_on
        if wants_pagination:
            print(f"  [naive] send({len(lines)} lines) -> PAGINATED (unexpected here)")
        else:
            print(f"  [naive] send({len(lines)} lines) -> sent whole, no MORE prompt")
        self.sent_pages.append(lines)


@dataclass
class BufferedContext:
    """Stand-in for the proposed fix: buffer within a turn, decide once."""
    more_prompt_on: bool = True
    _turn_buffer: list[str] = field(default_factory=list)
    flushed_pages: list[list[str]] = field(default_factory=list)  # what actually went out, one flush = one "screenful" decision

    def send(self, lines: list[str]) -> None:
        print(f"  [buffered] send({len(lines)} lines) -> buffered (turn total now {len(self._turn_buffer) + len(lines)})")
        self._turn_buffer.extend(lines)

    def flush_turn(self) -> None:
        """Call once at the natural end of a turn (e.g. right before the
        next ctx.prompt()) -- this is where the real fix would hook in."""
        total = self._turn_buffer
        wants_pagination = len(total) > PAGE_SIZE and self.more_prompt_on
        if wants_pagination:
            print(f"  [buffered] flush_turn(): {len(total)} lines total -> PAGINATED (More Prompt triggers)")
        else:
            print(f"  [buffered] flush_turn(): {len(total)} lines total -> sent whole")
        self.flushed_pages.append(total)
        self._turn_buffer = []


def run_command(ctx, help_lines: list[str], menu_lines: list[str]) -> None:
    """Simulates prefs.py-style flow: a help function sends its text, then
    a menu-display function sends its own text right after, in the same
    command dispatch."""
    ctx.send(help_lines)   # e.g. the 'h<key>' help text
    ctx.send(menu_lines)   # e.g. the menu redraw immediately after


def main() -> None:
    help_lines = [f"help line {i}" for i in range(20)]
    menu_lines = [f"menu line {i}" for i in range(20)]

    print(f"page_size = {PAGE_SIZE}, More Prompt = on, two send() calls of 20 lines each (40 total)\n")

    print("Today's behavior (NaiveContext):")
    naive = NaiveContext()
    run_command(naive, help_lines, menu_lines)
    triggered = any(len(page) > PAGE_SIZE for page in naive.sent_pages)
    print(f"  -> More Prompt triggered? {triggered}  (BUG: should be True, 40 lines is a full screenful)\n")

    print("Proposed fix (BufferedContext):")
    buffered = BufferedContext()
    run_command(buffered, help_lines, menu_lines)
    buffered.flush_turn()  # what a real end-of-turn hook (e.g. before next ctx.prompt()) would call
    triggered = any(len(page) > PAGE_SIZE for page in buffered.flushed_pages)
    print(f"  -> More Prompt triggered? {triggered}  (fixed: 40 lines correctly seen as one screenful)")


if __name__ == "__main__":
    main()
