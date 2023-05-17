import text_editor
import text_editor.functions


class CtrlFunction:
    def __init__(self, old_text: str):
        """
        Some ctrl key functions delete or otherwise manipulate text, so
        preserve text at entry in old_text in case editing is aborted

        :param old_text:
        :param new_text:
        """
        self.old_text = old_text
        self.new_text = new_text

    def delete_word_left(self, old_text: str, index: int):
        """
        from index in string, search backwards for " ".
        if found, delete from [" ":index]
        if not found, delete from [:index].
        Output "out_backspace([count])" backspaces to erase word from screen.

        :param old_text: the original string
        :param index: where the cursor is
        :return: new_text, the edited string.
        new_line, text that word-wrapped to next line
        """
        """
        >>> import text_editor

        >>> test = text_editor.Editor()

        >>> test.line_input = "duplicate word word"

        >>> original_length = len(test.line_input)

        >>> original_length
        19

        # find length of string so we can determine how many backspaces to
        # output (the difference of this and the length of the word being
        # deleted)
        >>> test.column = text_editor.find_nth(test.line_input, "word", 2)  # second space
        15

        """
        index = text_editor.text_editor.editor.column
        # at beginning of line, it's pointless, so do nothing:
        if index == 0:
            return old_text
        found_pos = text_editor.functions.search_backwards(old_text, index, " ")
        # TODO: finish this
        if found_pos:
            pass
        else:
            pass

        # original_length = len(old_text)
