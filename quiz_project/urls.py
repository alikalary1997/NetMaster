from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Import necessary views and forms for authentication customization
from django.contrib.auth.views import LoginView, PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView
from quiz.forms import CustomAuthenticationForm
from quiz.views import landing_page, signup_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', landing_page, name='landing_page'),

    # --- Authentication URLs ---
    path('accounts/signup/', signup_view, name='signup'),
    path('accounts/login/', LoginView.as_view(
        template_name='registration/login.html',
        authentication_form=CustomAuthenticationForm
    ), name='login'),

    # Custom password reset (explicit templates to avoid Django admin template collision)
    path('accounts/password_reset/', PasswordResetView.as_view(
        template_name='quiz/password_reset_form.html',
        email_template_name='quiz/password_reset_email.html',
        subject_template_name='quiz/password_reset_subject.txt',
    ), name='password_reset'),
    path('accounts/password_reset/done/', PasswordResetDoneView.as_view(
        template_name='quiz/password_reset_done.html'
    ), name='password_reset_done'),
    path('accounts/reset/<uidb64>/<token>/', PasswordResetConfirmView.as_view(
        template_name='quiz/password_reset_confirm.html'
    ), name='password_reset_confirm'),
    path('accounts/reset/done/', PasswordResetCompleteView.as_view(
        template_name='quiz/password_reset_complete.html'
    ), name='password_reset_complete'),

    # Include Django's default auth URLs (login/password_reset are overridden above)
    path('accounts/', include('django.contrib.auth.urls')),
    # --- END Authentication URLs ---

    path('quiz/', include('quiz.urls')),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)