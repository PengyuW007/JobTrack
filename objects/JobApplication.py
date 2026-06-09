class JobApplication:

    def __init__(
            self,
            gmail_id,
            company,
            position,
            sender,
            email_date,
            status,
            interview_count,
            offer,
            subject,
            body_preview
    ):
        self.gmail_id = gmail_id
        self.company = company
        self.position = position
        self.sender = sender
        self.email_date = email_date
        self.status = status
        self.interview_count = interview_count
        self.offer = offer
        self.subject = subject
        self.body_preview = body_preview

    def __str__(self):
        return (
            f"JobApplication("
            f"company={self.company}, "
            f"position={self.position}, "
            f"status={self.status}, "
            f"subject={self.subject}"
            f")"
        )

    def __repr__(self):
        return self.__str__()