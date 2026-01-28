from django import forms

from .models import MAX_COMMENT_LENGTH, Comment


class CommentForm(forms.ModelForm):
    parent_id = forms.UUIDField(
        required=False,
        widget=forms.HiddenInput,
    )
    website = forms.CharField(
        required=False,
        label="Website",
        widget=forms.TextInput(
            attrs={
                "autocomplete": "url",
                "class": "input-field website_",
                "value": "",
            }
        ),
    )

    class Meta:
        model = Comment
        fields = ["body"]
        widgets = {
            "body": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": "Yorumunuzu yazın...(Maksimum 3000 karakter)",
                }
            )
        }

    def clean_body(self):
        text = (self.cleaned_data.get("body") or "").strip()
        if len(text) > MAX_COMMENT_LENGTH:
            raise forms.ValidationError(
                f"Yorum en fazla {MAX_COMMENT_LENGTH} karakter olabilir."
            )
        return text
