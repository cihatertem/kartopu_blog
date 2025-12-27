from django import forms

from .models import MAX_COMMENT_LENGTH, Comment


class CommentForm(forms.ModelForm):
    website = forms.CharField(
        required=False,
        label="Website",
        widget=forms.TextInput(
            attrs={
                "autocomplete": "off",
                "tabindex": "-1",
                "style": "position:absolute; left:-10000px; top:auto; width:1px; height:1px; overflow:hidden;",
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
