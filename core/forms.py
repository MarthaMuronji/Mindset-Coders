from django import forms

class ContactForm(forms.Form):
    name = forms.CharField(max_length=100)
    email = forms.EmailField()
    role = forms.ChoiceField(choices=[
        ('school', 'School'),
        ('educator', 'Educator'),
        ('parent', 'Parent/Guardian'),
        ('partner', 'Partner/Organization'),
        ('other', 'Other'),
    ])
    message = forms.CharField(widget=forms.Textarea)