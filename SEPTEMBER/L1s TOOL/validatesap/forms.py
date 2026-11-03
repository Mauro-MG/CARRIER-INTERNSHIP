from django import forms


class ValidationForm(forms.Form):
    tumbling = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "tumbling-input",
                "placeholder": "A1234",
                "maxlength": 5,
                "size": 5,
                "autocomplete": "off",
                "spellcheck": "false",
            }
        ),
    )
    adds = forms.CharField(required=False, widget=forms.Textarea(attrs={"placeholder": "Item\tPart Number\tQuantity\tSource\n0010\tPN-1001\t1\tR", "rows": 7}))
    deletes = forms.CharField(required=False, widget=forms.Textarea(attrs={"placeholder": "Item\tPart Number\tQuantity\n0020\tPN-1002\t2", "rows": 7}))
    standard = forms.CharField(required=False, widget=forms.Textarea(attrs={"placeholder": "Level\tItem\tPart Number\tDescription\tQuantity\n1\t0010\tPN-1001\tExample component\t1", "rows": 8}))
    sap = forms.CharField(required=False, widget=forms.Textarea(attrs={"placeholder": "Level\tItem\tPart Number\tDescription\tQty\tUnit\tPGr\tSC1\tSC2\n1\t0010\tPN-1001\tExample component\t1\tEA\t001\t\t", "rows": 8}))
