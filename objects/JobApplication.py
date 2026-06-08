class JobApplication:
    def __init__(
            self,
            gmail_id,
            company,
            position,
            email_date,
            status,
            interview_count,
            offer,
            subject
    ):
        self.gmail_id = gmail_id
        self.company = company
        self.position = position
        self.email_date = email_date
        self.status = status
        self.interview_count = interview_count
        self.offer = offer
        self.subject = subject