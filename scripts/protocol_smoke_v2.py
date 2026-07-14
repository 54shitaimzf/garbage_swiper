def frame(kind, data=''):
    body = '01' + kind + f'{len(data) + 2:02X}' + data
    checksum = sum(int(body[i:i + 2], 16) for i in range(0, len(body), 2)) & 255
    return f'${body}{checksum:02X}#'

assert frame('10', '5000') == '$011006500067#'
assert frame('10', '9C00') == '$0110069C0063#'
assert frame('15', '07') == '$0115040721#'
print('official TCP frame checks: PASS')
