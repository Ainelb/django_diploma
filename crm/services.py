from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone

from accounts.models import Profile
from accounts.roles import is_head_or_admin

from .models import Deal, DealStatusHistory, Interaction, Task


class BusinessError(Exception):
    """Ошибка бизнес-правила, текст показывается пользователю."""


def deals_for(user):
    """Руководитель и админ видят все сделки, менеджер - только свои."""
    qs = Deal.objects.select_related('client', 'car_model', 'source', 'manager')
    if not user.is_authenticated:
        return qs.none()
    if is_head_or_admin(user):
        return qs
    return qs.filter(manager=user)


def tasks_for(user):
    qs = Task.objects.select_related('deal__client', 'assignee')
    if not user.is_authenticated:
        return qs.none()
    if is_head_or_admin(user):
        return qs
    return qs.filter(assignee=user)


@transaction.atomic
def create_deal(*, user, **data):
    """Процесс создания сделки - если создает менеджер, то она сразу закрепляется за ним, руководитель отдела продаж может сам указывать менеджера при создании сделки"""
    if not is_head_or_admin(user):
        data['manager'] = user
    deal = Deal.objects.create(status=Deal.Status.NEW, **data)
    DealStatusHistory.objects.create(
        deal=deal, from_status='', to_status=Deal.Status.NEW, changed_by=user, comment='Сделка создана'
    )
    return deal


@transaction.atomic
def change_deal_status(deal, new_status, *, user, comment='', amount=None, lost_reason=''):
    """Перевод сделки в новый статус с проверкой правил воронки и записью в историю."""
    if new_status not in Deal.Status.values:
        raise BusinessError(f'Неизвестный статус: {new_status}.')
    if new_status == deal.status:
        raise BusinessError('Сделка уже находится в этом статусе.')
    if not deal.can_transition_to(new_status):
        allowed = ', '.join(Deal.Status(s).label for s in deal.allowed_statuses) or 'нет'
        raise BusinessError(
            f'Нельзя перевести сделку из «{deal.get_status_display()}» в '
            f'«{Deal.Status(new_status).label}». Допустимые переходы: {allowed}.'
        )
    if new_status == Deal.Status.WON:
        if amount is None and deal.amount is None:
            raise BusinessError('Чтобы закрыть сделку как проданную, укажите сумму сделки.')
        if amount is not None and amount <= 0:
            raise BusinessError('Сумма сделки должна быть больше нуля.')
    if new_status == Deal.Status.LOST and not (lost_reason or '').strip():
        raise BusinessError('Укажите причину отказа.')

    old_status = deal.status
    deal.status = new_status
    if amount is not None:
        deal.amount = amount
    if new_status == Deal.Status.LOST:
        deal.lost_reason = lost_reason.strip()
    if new_status in Deal.CLOSED_STATUSES:
        deal.closed_at = timezone.now()
    else:
        deal.closed_at = None
        deal.lost_reason = ''
    deal.save()

    DealStatusHistory.objects.create(
        deal=deal, from_status=old_status, to_status=new_status, changed_by=user, comment=comment
    )
    return deal


@transaction.atomic
def assign_manager(deal, manager, *, user):
    """Назначение менеджера (только руководитель или админ)."""
    if not is_head_or_admin(user):
        raise BusinessError('Назначать менеджера может только руководитель или администратор.')
    if not manager.is_active:
        raise BusinessError('Нельзя назначить заблокированного пользователя.')
    if manager.profile.role not in (Profile.Role.MANAGER, Profile.Role.HEAD):
        raise BusinessError('Ответственным может быть только менеджер или руководитель.')
    if deal.is_closed:
        raise BusinessError('Сделка уже закрыта - менять ответственного нельзя.')
    previous = deal.manager
    deal.manager = manager
    deal.save(update_fields=['manager', 'updated_at'])
    Interaction.objects.create(
        deal=deal,
        kind=Interaction.Kind.NOTE,
        author=user,
        comment=f'Ответственный изменён: {previous.get_full_name() if previous else "не назначен"}'
                f' → {manager.get_full_name() or manager.username}',
    )
    return deal


def complete_task(task, *, user):
    if task.is_done:
        raise BusinessError('Задача уже выполнена.')
    task.is_done = True
    task.done_at = timezone.now()
    task.save(update_fields=['is_done', 'done_at'])
    return task


# Для аналитики сделок

def _with_conversion(rows):
    for row in rows:
        closed = row['won'] + row['lost']
        row['conversion'] = round(row['won'] / row['total'] * 100, 1) if row['total'] else 0.0
        row['win_rate_closed'] = round(row['won'] / closed * 100, 1) if closed else 0.0
        row['revenue'] = int(row['revenue'] or 0)
    return rows


def _grouped(qs, *fields):
    return _with_conversion(list(
        qs.values(*fields)
        .annotate(
            total=Count('id'),
            won=Count('id', filter=Q(status=Deal.Status.WON)),
            lost=Count('id', filter=Q(status=Deal.Status.LOST)),
            revenue=Sum('amount', filter=Q(status=Deal.Status.WON)),
        )
        .order_by('-total')
    ))


def analytics_summary(qs):
    """Выводы по сделкам:
    conversion - доля проданных от всех лидов;
    win_rate_closed - доля проданных среди закрытых сделок (продан + отказ).
    """
    total = qs.count()
    by_status = {row['status']: row['n'] for row in qs.values('status').annotate(n=Count('id'))}
    funnel = [
        {'status': s.value, 'label': s.label, 'count': by_status.get(s.value, 0)}
        for s in Deal.Status
    ]
    won = by_status.get(Deal.Status.WON, 0)
    revenue = qs.filter(status=Deal.Status.WON).aggregate(s=Sum('amount'))['s'] or 0
    return {
        'total_deals': total,
        'won': won,
        'lost': by_status.get(Deal.Status.LOST, 0),
        'conversion': round(won / total * 100, 1) if total else 0.0,
        'revenue': int(revenue),
        'average_check': int(revenue / won) if won else 0,
        'funnel': funnel,
        'by_source': _grouped(qs, 'source__id', 'source__name'),
        'by_manager': _grouped(qs, 'manager__id', 'manager__username', 'manager__first_name', 'manager__last_name'),
        'by_car_model': _grouped(qs, 'car_model__id', 'car_model__brand', 'car_model__name'),
    }