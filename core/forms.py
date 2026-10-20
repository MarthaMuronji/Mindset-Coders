from django import forms

from .models import Story

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


class StoryForm(forms.ModelForm):
    """The Share your story form.

    The honeypot field is declared but never listed in Meta.fields, so what
    a bot types into it can never reach the model, and there is no file
    field anywhere, so no photo can be uploaded.
    """

    # The model-derived checkbox would come out as required=False (Django
    # allows unchecked checkboxes), so consent is declared here to be a
    # real required checkbox
    consent = forms.BooleanField(
        required=True,
        label='I agree that Mindset Coders may publish my story on this website after reviewing it. If it includes a child under 18, I am their parent or guardian, or I have their permission.',
    )

    # Spam trap, rendered hidden by the .honeypot-field wrapper in the template
    website = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'tabindex': '-1',
            'autocomplete': 'off',
        }),
    )

    class Meta:
        model = Story
        # consent is declared above; approved and created_at stay out
        fields = ('name', 'email', 'role', 'category', 'story', 'display_as', 'consent')
        labels = {
            'name': 'Your name',
            'email': 'Your email (we never show this)',
            'role': 'I am a',
            'category': 'What is your story about?',
            'story': 'Your story',
            'display_as': 'How should we show your name if we publish your story?',
        }
        help_texts = {
            'story': 'A few sentences is enough. Please do not include phone numbers or home addresses.',
        }
        widgets = {
            'story': forms.Textarea(attrs={'rows': 8}),
        }


class ReviewStoryForm(forms.ModelForm):
    """The parts of a story the team may edit, validated like the share form.

    name, email and consent are never editable here: they belong to the
    person who sent the story in.
    """

    class Meta:
        model = Story
        fields = ('story', 'category', 'display_as')
        labels = {
            'story': 'Your story',
            'category': 'What is your story about?',
            'display_as': 'How should we show your name if we publish your story?',
        }
        widgets = {
            'story': forms.Textarea(attrs={'rows': 8}),
        }