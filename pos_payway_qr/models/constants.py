# Part of Odoo. See LICENSE file for full copyright and licensing details.

# The keys of the values to use in the calculation of the signature.
SIGNATURE_KEYS = {
    'outgoing': [
        'req_time',
        'merchant_id',
        'tran_id',
        'amount',
        'items',
        'payment_option',
        'return_url',
        'cancel_url',
        'continue_success_url',
        'currency',
        'return_params',
        'lifetime',
    ],
    'incoming': [
        'req_time',
        'merchant_id',
        'tran_id',
    ],
}

# Mapping of transaction states to PayWay success codes.
PAYMENT_STATUS = {
    'approved': 'APPROVED',
    'declined': 'DECLINED',
    'pending': 'PENDING',
}

SUCCESS_CODE_MAPPING = {
    'done': ('APPROVED', 0),
    'error': ('PENDING', 'DECLINED'),
}
