"""bright_assignments URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf.urls import url
from django.contrib.auth import views as auth_views
from django.urls import path
from plaid_api import views

urlpatterns = [
    url(r'^login/$', auth_views.LoginView.as_view(), name='login'),
    url(r'^logout/$', auth_views.LogoutView.as_view(), name='logout'),
    path('admin/', admin.site.urls),
    path('get_access_token', views.get_access_token, name='get_access_token'),
    path('create_link_token', views.create_link_token, name='create_link_token'),
    path('fetch_transactions', views.get_transaction_from_db, name='fetch_transactions'),
    path('get_account_info', views.get_account_info, name='get_account_info'),
    url(r'^signup/$', views.signup, name='signup'),
    url(r'^$', views.home, name='home'),
]
