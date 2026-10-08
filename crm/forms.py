from django import forms
from django.contrib.auth.models import User

from accounts.models import Profile

from .models import CarModel, Client, Deal, Interaction, LeadSource, Task


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['full_name', 'phone', 'email', 'city']
        widgets = {'phone': forms.TextInput(attrs={'placeholder': '+77011234567'})}


class DealForm(forms.ModelForm):
    class Meta:
        model = Deal
        fields = ['client', 'car_model', 'source', 'manager']

    def __init__(self, *args, can_assign=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['car_model'].queryset = CarModel.objects.filter(is_active=True)
        self.fields['source'].queryset = LeadSource.objects.filter(is_active=True)
        if can_assign:
            self.fields['manager'].queryset = User.objects.filter(
                is_active=True, profile__role__in=[Profile.Role.MANAGER, Profile.Role.HEAD]
            )
            self.fields['manager'].required = False
        else:
            del self.fields['manager']


class StatusForm(forms.Form):
    status = forms.ChoiceField(label='Новый статус')
    amount = forms.DecimalField(label='Сумма сделки, ₸', required=False, min_value=1, decimal_places=0)
    lost_reason = forms.CharField(label='Причина отказа', required=False, max_length=255)
    comment = forms.CharField(label='Комментарий', required=False, max_length=255)

    def __init__(self, *args, deal=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['status'].choices = [(s, Deal.Status(s).label) for s in deal.allowed_statuses]


class InteractionForm(forms.ModelForm):
    class Meta:
        model = Interaction
        fields = ['kind', 'comment']
        widgets = {'comment': forms.Textarea(attrs={'rows': 3, 'placeholder': 'О чём договорились'})}


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title', 'due_date']
        widgets = {'due_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M')}