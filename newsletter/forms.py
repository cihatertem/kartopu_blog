from django import forms


class NewsletterEmailForm(forms.Form):
    email = forms.EmailField(
        label="E-posta",
        widget=forms.EmailInput(attrs={"placeholder": "E-posta adresiniz"}),
    )
