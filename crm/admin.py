from django.contrib import admin

from .models import CarModel, Client, Deal, DealStatusHistory, Interaction, LeadSource, Task


@admin.register(CarModel)
class CarModelAdmin(admin.ModelAdmin):
    list_display = ('brand', 'name', 'body_type', 'base_price', 'is_active')
    list_filter = ('brand', 'body_type', 'is_active')
    search_fields = ('brand', 'name')


@admin.register(LeadSource)
class LeadSourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'channel', 'is_active')
    list_filter = ('channel', 'is_active')


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'phone', 'email', 'city', 'created_at')
    search_fields = ('full_name', 'phone', 'email')
    list_filter = ('city',)


class HistoryInline(admin.TabularInline):
    model = DealStatusHistory
    extra = 0
    readonly_fields = ('from_status', 'to_status', 'changed_by', 'comment', 'changed_at')
    can_delete = False


class InteractionInline(admin.TabularInline):
    model = Interaction
    extra = 0


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = ('id', 'client', 'car_model', 'source', 'manager', 'status', 'amount', 'created_at')
    list_filter = ('status', 'source', 'car_model__brand', 'manager')
    search_fields = ('client__full_name', 'client__phone')
    date_hierarchy = 'created_at'
    inlines = [HistoryInline, InteractionInline]
    readonly_fields = ('created_at', 'updated_at', 'closed_at')


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'assignee', 'due_date', 'is_done')
    list_filter = ('is_done', 'assignee')
    search_fields = ('title',)


@admin.register(Interaction)
class InteractionAdmin(admin.ModelAdmin):
    list_display = ('deal', 'kind', 'author', 'created_at')
    list_filter = ('kind',)