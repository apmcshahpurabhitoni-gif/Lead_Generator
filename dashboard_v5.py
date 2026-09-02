import dashboard_v4 as _base

# The previous search required the whole query to be one contiguous string.
# That made a natural query such as "Jabalpur clinic" fail because the stored
# lead has city and industry as separate fields. Match every search token
# independently so business/city/category combinations work naturally.
_old = "return !q||z.toLowerCase().includes(q)"
_new = "return !q||q.split(/\\s+/).filter(Boolean).every(t=>z.toLowerCase().includes(t))"
_base.PAGE = _base.PAGE.replace(_old, _new)

router = _base.router
