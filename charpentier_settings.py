"""Public score settings; these intervals apply only to the generated study."""
INTERVALS = {-5:'-P4', -3:'-m3', -2:'-M2', -1:'-m2', 0:'P1', 1:'m2',
             2:'M2', 3:'m3', 4:'M3', 5:'P4'}
# Public minor shift values are relative to A, the relative minor of C major.
# Canonical composition uses C minor to keep the four voices in their usual register.
MINOR_INTERVALS = {0:'-m3', 2:'-m2', 3:'P1', 5:'M2'}
METERS = ('4/4', '2/2', '2/4', '3/4', '6/8')


def meter_family(meter):
    return '4/4' if meter == '2/2' else meter
