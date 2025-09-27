# hdr_app/middleware.py
class CSPMiddleware:
    """Custom Content Security Policy middleware for Alpine.js compatibility"""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Set CSP header to allow Alpine.js
        csp_policy = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
            "img-src 'self' data: blob:; "
            "connect-src 'self'; "
            "font-src 'self' https://cdnjs.cloudflare.com; "
            "object-src 'none'; "
            "base-uri 'self';"
        )
        
        response['Content-Security-Policy'] = csp_policy
        return response