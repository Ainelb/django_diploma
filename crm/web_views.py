from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.roles import is_head_or_admin

from . import services
from .forms import ClientForm, DealForm, InteractionForm, StatusForm, TaskForm
from .models import Deal, LeadSource


@login_required
def dashboard(request):
    deals = services.deals_for(request.user)
    stats = services.analytics_summary(deals)
    max_count = max((s['count'] for s in stats['funnel']), default=0) or 1
    for step in stats['funnel']:
        step['width'] = max(round(step['count'] / max_count * 100), 2)
    tasks = services.tasks_for(request.user).filter(assignee=request.user, is_done=False)
    return render(request, 'crm/dashboard.html', {
        'stats': stats,
        'tasks_today': tasks.filter(due_date__date=timezone.localdate()),
        'tasks_overdue': tasks.filter(due_date__lt=timezone.now()).exclude(due_date__date=timezone.localdate()),
        'recent_deals': deals[:6],
    })


@login_required
def deal_list(request):
    deals = services.deals_for(request.user)
    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    source = request.GET.get('source', '')
    if q:
        deals = deals.filter(Q(client__full_name__icontains=q) | Q(client__phone__icontains=q)
                             | Q(car_model__name__icontains=q) | Q(car_model__brand__icontains=q))
    if status:
        deals = deals.filter(status=status)
    if source:
        deals = deals.filter(source_id=source)
    page = Paginator(deals, 15).get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)
    return render(request, 'crm/deal_list.html', {
        'page': page, 'q': q, 'status': status, 'source': source,
        'statuses': Deal.Status.choices, 'sources': LeadSource.objects.all(),
        'querystring': params.urlencode(),
    })


@login_required
def deal_detail(request, pk):
    deal = get_object_or_404(services.deals_for(request.user), pk=pk)
    # шкала этапов: пройденные, текущий и будущие
    order = [s for s in Deal.Status if s != Deal.Status.LOST]
    reached = set(deal.history.values_list('to_status', flat=True))
    steps = [{'label': s.label,
              'state': 'current' if s == deal.status else ('done' if s in reached else 'todo')}
             for s in order]
    return render(request, 'crm/deal_detail.html', {
        'deal': deal,
        'steps': steps,
        'status_form': StatusForm(deal=deal) if deal.allowed_statuses else None,
        'interaction_form': InteractionForm(),
        'task_form': TaskForm(),
        'history': deal.history.select_related('changed_by'),
        'interactions': deal.interactions.select_related('author'),
        'tasks': deal.tasks.select_related('assignee'),
    })


@login_required
def deal_create(request):
    can_assign = is_head_or_admin(request.user)
    deal_form = DealForm(request.POST or None, can_assign=can_assign, prefix='deal')
    client_form = ClientForm(prefix='client')
    if request.method == 'POST':
        new_client = request.POST.get('new_client') == '1'
        if new_client:
            client_form = ClientForm(request.POST, prefix='client')
            deal_form.fields['client'].required = False
        if deal_form.is_valid() and (not new_client or client_form.is_valid()):
            data = dict(deal_form.cleaned_data)
            if new_client:
                data['client'] = client_form.save(commit=False)
                data['client'].created_by = request.user
                data['client'].save()
            if not data.get('manager'):
                data.pop('manager', None)
            deal = services.create_deal(user=request.user, **data)
            messages.success(request, f'Сделка #{deal.pk} создана.')
            return redirect('deal_detail', pk=deal.pk)
    return render(request, 'crm/deal_form.html', {'deal_form': deal_form, 'client_form': client_form})


@login_required
@require_POST
def deal_change_status(request, pk):
    deal = get_object_or_404(services.deals_for(request.user), pk=pk)
    form = StatusForm(request.POST, deal=deal)
    if form.is_valid():
        try:
            services.change_deal_status(
                deal, form.cleaned_data['status'], user=request.user,
                comment=form.cleaned_data['comment'], amount=form.cleaned_data['amount'],
                lost_reason=form.cleaned_data['lost_reason'],
            )
            messages.success(request, f'Статус изменён на «{deal.get_status_display()}».')
        except services.BusinessError as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, 'Проверьте данные формы.')
    return redirect('deal_detail', pk=pk)


@login_required
@require_POST
def deal_add_interaction(request, pk):
    deal = get_object_or_404(services.deals_for(request.user), pk=pk)
    form = InteractionForm(request.POST)
    if form.is_valid():
        interaction = form.save(commit=False)
        interaction.deal = deal
        interaction.author = request.user
        interaction.save()
        messages.success(request, 'Касание добавлено.')
    else:
        messages.error(request, 'Заполните комментарий.')
    return redirect('deal_detail', pk=pk)


@login_required
@require_POST
def deal_add_task(request, pk):
    deal = get_object_or_404(services.deals_for(request.user), pk=pk)
    form = TaskForm(request.POST)
    if form.is_valid():
        if form.cleaned_data['due_date'] < timezone.now():
            messages.error(request, 'Срок задачи не может быть в прошлом.')
        else:
            task = form.save(commit=False)
            task.deal = deal
            task.assignee = deal.manager or request.user
            task.created_by = request.user
            task.save()
            messages.success(request, 'Задача поставлена.')
    else:
        messages.error(request, 'Укажите название и срок задачи.')
    return redirect('deal_detail', pk=pk)


@login_required
def task_list(request):
    tasks = services.tasks_for(request.user)
    show = request.GET.get('show', 'open')
    if show == 'open':
        tasks = tasks.filter(is_done=False)
    elif show == 'done':
        tasks = tasks.filter(is_done=True)
    return render(request, 'crm/task_list.html', {'tasks': tasks[:100], 'show': show})


@login_required
@require_POST
def task_complete(request, pk):
    task = get_object_or_404(services.tasks_for(request.user), pk=pk)
    try:
        services.complete_task(task, user=request.user)
        messages.success(request, 'Задача выполнена.')
    except services.BusinessError as exc:
        messages.error(request, str(exc))
    return redirect(request.POST.get('next') or 'task_list')