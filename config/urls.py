from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

admin.site.site_header = 'CRM дилерского центра'
admin.site.site_title = 'CRM дилерского центра'

urlpatterns = [
    path('admin/', admin.site.urls),
    # REST API
    path('api/', include('accounts.urls')),
    path('api/', include('crm.api_urls')),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api-auth/', include('rest_framework.urls')),
    # HTML-интерфейс
    path('login/', auth_views.LoginView.as_view(template_name='auth/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', include('crm.web_urls')),
]