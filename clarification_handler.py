class ClarificationHandler:
    def needs_clarification(self, response):
        unclear_phrases = ["unsure", "cannot determine", "ambiguous"]
        return any(phrase in response.lower() for phrase in unclear_phrases)

    def request_clarification(self):
        return input("Your request is ambiguous. Please provide more details: ")
