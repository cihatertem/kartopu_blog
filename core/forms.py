from django import forms

from .models import ContactMessage


class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ["name", "subject", "email", "message", "website"]

    def clean_name(self):
        return (self.cleaned_data.get("name") or "").strip()

    def clean_subject(self):
        return (self.cleaned_data.get("subject") or "").strip()

    def clean_message(self):
        text = (self.cleaned_data.get("message") or "").strip()
        if len(text) > ContactMessage.MAX_MESSAGE_LENGTH:
            raise forms.ValidationError(
                f"Mesaj en fazla {ContactMessage.MAX_MESSAGE_LENGTH} karakter olabilir."
            )
        return text

    def clean_website(self):
        return (self.cleaned_data.get("website") or "").strip()
