from django import forms


class NewsletterEmailForm(forms.Form):
    email = forms.EmailField(
        label="E-posta",
        widget=forms.EmailInput(attrs={"placeholder": "E-posta adresiniz"}),
    )
    name = forms.CharField(
        label="name",
        max_length=100,
        widget=forms.TextInput(
            attrs={"class": "input-field name_", "autocomplete": "off"}
        ),
        required=False,
    )
