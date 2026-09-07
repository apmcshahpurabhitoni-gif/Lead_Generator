"""LeadHunter dashboard authentication, CSRF and failed-login throttling."""
import os,secrets,time
from collections import defaultdict,deque
from fastapi import HTTPException,Request
_attempts=defaultdict(deque);WINDOW=300;MAX_ATTEMPTS=5
def enabled():return os.getenv("DASHBOARD_AUTH_ENABLED","true").lower()=="true"
def production():return os.getenv("ENVIRONMENT","development").lower()=="production"
def validate_auth_config():
 if production() and not enabled():raise RuntimeError("DASHBOARD_AUTH_ENABLED cannot be false in production")
 if enabled():
  missing=[k for k in ("DASHBOARD_USER","DASHBOARD_PASSWORD","SESSION_SECRET") if not os.getenv(k,"").strip()]
  if missing:raise RuntimeError("Missing dashboard authentication variables: "+", ".join(missing))
def verify_credentials(username,password):
 return bool(os.getenv("DASHBOARD_USER","") and os.getenv("DASHBOARD_PASSWORD","") and secrets.compare_digest(username,os.getenv("DASHBOARD_USER","")) and secrets.compare_digest(password,os.getenv("DASHBOARD_PASSWORD","")))
def _key(request):return request.client.host if request.client else "unknown"
def check_login_rate_limit(request):
 now=time.time();q=_attempts[_key(request)]
 while q and now-q[0]>WINDOW:q.popleft()
 if len(q)>=MAX_ATTEMPTS:raise HTTPException(429,"Too many failed login attempts. Try again later.")
def record_login_failure(request):
 now=time.time();q=_attempts[_key(request)];q.append(now)
def clear_login_failures(request):_attempts.pop(_key(request),None)
def require_dashboard_auth(request):
 if enabled() and not request.session.get("authenticated"):raise HTTPException(401,"Authentication required")
def require_csrf(request):
 if not enabled():return
 token=request.headers.get("X-CSRF-Token","");expected=request.session.get("csrf_token","")
 if not expected or not token or not secrets.compare_digest(token,expected):raise HTTPException(403,"Invalid CSRF token")
def create_session(request,username):
 request.session.clear();request.session.update({"authenticated":True,"username":username,"csrf_token":secrets.token_urlsafe(32)})
