"""Authoritative server-side definitions for attendance break reasons.
Aligned with BEYONDSURE HRMS specification.
"""

BREAK_REASONS = {
    'lunch': {
        'label': 'Lunch',
        'description': 'The midday break.',
        'duration_limit_minutes': 40,
        'counts_as_worked_time': False,
    },
    'tea_coffee': {
        'label': 'Tea or coffee',
        'description': 'A short break away from the desk.',
        'duration_limit_minutes': 10,
        'counts_as_worked_time': False,
    },
    'outside_meeting': {
        'label': 'Outside meeting',
        'description': 'A meeting away from the office.',
        'duration_limit_minutes': None,
        'counts_as_worked_time': True,
    },
    'client_visit': {
        'label': 'Client visit',
        'description': 'At a client’s premises.',
        'duration_limit_minutes': None,
        'counts_as_worked_time': True,
    },
    'client_call': {
        'label': 'Client — telephonic call',
        'description': 'On a call with a client.',
        'duration_limit_minutes': 30,
        'counts_as_worked_time': True,
    },
    'personal_call': {
        'label': 'Personal telephonic call',
        'description': 'A personal call.',
        'duration_limit_minutes': 10,
        'counts_as_worked_time': False,
    },
    'team_meeting': {
        'label': 'Team meeting',
        'description': 'An internal meeting.',
        'duration_limit_minutes': None,
        'counts_as_worked_time': True,
    },
    'training': {
        'label': 'Product training',
        'description': 'Learning or delivering training.',
        'duration_limit_minutes': None,
        'counts_as_worked_time': True,
    },
    'paperwork': {
        'label': 'Paperwork',
        'description': 'Away from the system doing paperwork.',
        'duration_limit_minutes': None,
        'counts_as_worked_time': True,
    },
    'other': {
        'label': 'Other',
        'description': 'Anything else — say what in the comment.',
        'duration_limit_minutes': 15,
        'counts_as_worked_time': False,
    },
}

BREAK_REASON_CHOICES = [
    (key, val['label']) for key, val in BREAK_REASONS.items()
]
