"""helpstaff — the HELPSTAFF subsystem behind commands/helpstaff.py.

  duty.py    who is helpstaff (the saved PlayerFlags.HELPSTAFF membership
             flag) vs. who is on duty right now (per-connection, never
             saved), the [Helpstaff] tag, and permission checks
  queue.py   questions asked while nobody was on duty, saved to
             helpstaff_queue.json in the save directory
  faq.py     pre-written answers staff can mail back, saved to
             helpstaff_faq.json in the save directory
  review.py  walking the queue and mailing answers back -- shared by
             'helpstaff #queue' and logon_events/helpstaff.py

Live requests (asked while someone *is* on duty) still live in
Server.pending_help_requests; only unanswered-by-anyone questions go to
the queue.
"""
