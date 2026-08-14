from django import forms
from django.contrib.auth.forms import (  # <--- IMPORT UserCreationForm here
    AuthenticationForm,
    UserCreationForm,
)
from django.contrib.auth.models import (
    User,  # Required for UserCreationForm's Meta class
)
from django.utils import timezone  # Needed for UserBlockForm's clean method

from .models import Answer, MatchingPair, Question, Test, UserProfile

# --- Custom Admin Forms ---


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ["test", "text", "image", "explanation", "question_type"]
        widgets = {
            "text": forms.Textarea(
                attrs={"rows": 4, "class": "textarea textarea-bordered w-full"}
            ),
            "explanation": forms.Textarea(
                attrs={"rows": 3, "class": "textarea textarea-bordered w-full"}
            ),
            "test": forms.Select(
                attrs={"class": "select select-bordered w-full max-w-xs"}
            ),
            "image": forms.FileInput(
                attrs={"class": "file-input file-input-bordered w-full max-w-xs"}
            ),
            "question_type": forms.Select(
                attrs={"class": "select select-bordered w-full max-w-xs"}
            ),
        }
        labels = {
            "test": "Assign to Test Type",
            "question_type": "Question Type",
        }


class AnswerForm(forms.ModelForm):
    class Meta:
        model = Answer
        fields = ["text", "is_correct"]
        widgets = {
            "text": forms.Textarea(
                attrs={
                    "class": "textarea textarea-bordered w-full resize-none overflow-hidden min-h-[2.5rem]",
                    "maxlength": "1000",
                    "placeholder": "Enter answer choice text (max 1000 characters)",
                    "rows": "1",
                    "oninput": "autoResize(this)",
                }
            ),
            "is_correct": forms.CheckboxInput(
                attrs={"class": "checkbox checkbox-primary"}
            ),
        }
        labels = {
            "text": "Answer Text",
            "is_correct": "Is Correct?",
        }

    def clean_text(self):
        text = self.cleaned_data.get("text")
        if text and len(text.strip()) < 1:
            raise forms.ValidationError("Answer text cannot be empty.")
        if text and len(text) > 1000:
            raise forms.ValidationError("Answer text must be 1000 characters or less.")
        return text.strip() if text else text


class TestForm(forms.ModelForm):
    """Form for creating and editing Test objects"""

    class Meta:
        model = Test
        fields = ["name", "description", "test_type"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "description": forms.Textarea(
                attrs={"rows": 4, "class": "textarea textarea-bordered w-full"}
            ),
            "test_type": forms.Select(
                attrs={"class": "select select-bordered w-full max-w-xs"}
            ),
        }
        labels = {
            "name": "Test Name",
            "description": "Description",
            "test_type": "Test Behavior Type",
        }


# --- Matching Pair Form ---


class MatchingPairForm(forms.ModelForm):
    class Meta:
        model = MatchingPair
        fields = ["left_text", "right_text"]
        widgets = {
            "left_text": forms.TextInput(
                attrs={
                    "class": "input input-bordered w-full",
                    "placeholder": "Left item (e.g., CCNA)",
                    "maxlength": "500",
                }
            ),
            "right_text": forms.TextInput(
                attrs={
                    "class": "input input-bordered w-full",
                    "placeholder": "Right match (e.g., Cisco Certified Network Associate)",
                    "maxlength": "500",
                }
            ),
        }
        labels = {
            "left_text": "Left Item",
            "right_text": "Right Item (correct match)",
        }


# --- Quiz Taking Form ---


class UserAnswerForm(forms.Form):
    selected_answers = forms.ModelMultipleChoiceField(
        queryset=Answer.objects.none(),  # Empty queryset initially
        widget=forms.CheckboxSelectMultiple(),  # Allows multiple selections
        required=False,  # User might not select anything (considered incorrect)
    )

    def __init__(self, *args, **kwargs):
        question = kwargs.pop(
            "question"
        )  # Get the question object passed from the view
        super().__init__(*args, **kwargs)
        # Set the queryset for the selected_answers field based on the question
        self.fields["selected_answers"].queryset = question.answers.all()
        # Add DaisyUI classes to checkboxes
        self.fields["selected_answers"].widget.attrs.update(
            {"class": "checkbox checkbox-primary mr-2"}
        )


# --- User Blocking Form ---


class UserBlockForm(forms.ModelForm):
    blocked_until = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "class": "input input-bordered w-full"}
        ),
        label="Block Until (Leave blank to block permanently)",
    )

    class Meta:
        model = UserProfile
        fields = ["blocked_until"]

    def clean_blocked_until(self):
        blocked_until = self.cleaned_data.get("blocked_until")
        if blocked_until and blocked_until < timezone.now():
            raise forms.ValidationError("Block until date cannot be in the past.")
        return blocked_until


# --- Custom Authentication Form for Login Page ---
class CustomAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Apply DaisyUI input classes to username and password fields
        self.fields["username"].widget.attrs.update(
            {
                "class": "input input-bordered w-full",
                "placeholder": "Enter your username",  # Optional placeholder
            }
        )
        self.fields["password"].widget.attrs.update(
            {
                "class": "input input-bordered w-full",
                "placeholder": "Enter your password",  # Optional placeholder
            }
        )


# --- NEW: Custom User Creation Form for Signup Page ---
class CustomUserCreationForm(UserCreationForm):
    phone = forms.CharField(
        max_length=10,
        required=True,
        label="Phone Number",
        widget=forms.TextInput(
            attrs={"placeholder": "7717000284", "inputmode": "numeric"}
        ),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ("phone",)

    def clean_phone(self):
        phone = self.cleaned_data.get("phone", "").strip()
        if not phone.isdigit() or len(phone) != 10:
            raise forms.ValidationError("Phone number must be exactly 10 digits.")
        return phone

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            placeholder_text = field.label or ""
            if field_name == "password2":
                placeholder_text = "Confirm Password"
            elif field_name == "password1":
                placeholder_text = "Password"
            elif field_name == "username":
                placeholder_text = "Choose a Username"
            elif field_name == "phone":
                placeholder_text = "7717000284"

            field.widget.attrs.update(
                {
                    "class": "input input-bordered w-full",
                    "placeholder": placeholder_text,
                }
            )
