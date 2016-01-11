from __future__ import division, absolute_import, print_function

import numpy as np


__all__ = ['parser']


INDEX_CHECKSUM = 2
INDEX_SYSTEMID = 4
INDEX_TMTYPE = 5
INDEX_PAYLOAD_LENGTH = 6
INDEX_COUNTER = 8
INDEX_SYSTIME = 10
INDEX_PAYLOAD = 16


def parser(packet, filter_systemid=None, filter_tmtype=None):
    buf = bytearray(packet)

    header = {'systemid' : buf[INDEX_SYSTEMID],
              'tmtype'   : buf[INDEX_TMTYPE],
              'counter'  : buf[INDEX_COUNTER]
                           | buf[INDEX_COUNTER + 1] << 8,
              'systime'  : buf[INDEX_SYSTIME]
                           | buf[INDEX_SYSTIME + 1] << 8
                           | buf[INDEX_SYSTIME + 2] << 16
                           | buf[INDEX_SYSTIME + 3] << 24
                           | buf[INDEX_SYSTIME + 4] << 32
                           | buf[INDEX_SYSTIME + 5] << 40
             }

    if filter_systemid is not None and filter_systemid != header['systemid']: return
    if filter_tmtype is not None and filter_tmtype != header['tmtype']: return

    # Card cage packet
    if header['systemid'] & 0xF0 == 0x80:
        # Event packet
        if header['tmtype'] == 0xF3: 
            return ge_event(buf, header)


def ge_event(buf, out):
    """Assumes only one event in each event packet
    """
    if ((out['systemid'] & 0xF0) != 0x80) or (out['tmtype'] != 0xF3):
        raise InputError

    index = INDEX_PAYLOAD

    out['detector'] = out['systemid'] & 0x0F

    out['veto_lvgr'] = buf[index] & 1
    out['veto_hvgr'] = buf[index] >> 1 & 1
    out['veto_shield'] = buf[index] >> 2 & 1
    out['veto_multiple'] = buf[index] >> 3 & 1

    time_lsb = buf[index] >> 7 | buf[index + 1] << 1 | buf[index + 2] << 9
    time_diff = (out['systime'] & ((1 << 17) - 1)) - time_lsb
    if time_diff < 0:
        time_diff += 1 << 17
    out['event_time'] = (out['systime'] - time_diff) * 10 + (buf[index] >> 3 & 0x0E)

    index += 3

    num_cha = np.zeros(8, np.uint8)
    for side in range(2):
        num_cha[4 * side + 0] = buf[index + 0] & 0x3F
        num_cha[4 * side + 1] = buf[index + 0] >> 6 | (buf[index + 1] & 0x0F) << 2
        num_cha[4 * side + 2] = buf[index + 1] >> 4 | (buf[index + 2] & 0x03) << 4
        num_cha[4 * side + 3] = buf[index + 2] >> 2
        index += 3

    asiccha = np.zeros(512, np.uint16)
    has_conversion = np.zeros(512, np.bool)
    has_trigger = np.zeros(512, np.bool)
    adc = np.zeros(512, np.uint16)
    has_glitch = np.zeros(512, np.bool)
    delta_time = np.zeros(512, np.int8)

    loc = 0

    for asic in range(8):
        for entry in range(num_cha[asic]):
            asiccha[loc] = (buf[index] & 0x3F) + asic * 64
            has_conversion[loc] = buf[index] >> 6 & 1
            has_trigger[loc] = buf[index] >> 7 & 1
            index += 1

            if has_conversion[loc]:
                adc[loc] = buf[index] | (buf[index + 1] & 0x7F) << 8
                has_glitch[loc] = buf[index + 1] >> 7
                index += 2

            if has_trigger[loc]:
                delta_time[loc] = buf[index]
                index += 1
            
            loc += 1

    out['asiccha'] = asiccha[:loc]
    out['has_conversion'] = has_conversion[:loc]
    out['has_trigger'] = has_trigger[:loc]
    out['adc'] = adc[:loc]
    out['has_glitch'] = has_glitch[:loc]
    out['delta_time'] = delta_time[:loc]

    return out
