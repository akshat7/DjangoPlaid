from django.contrib import admin
from .models import PlaidItem, UserAccount, Transaction
# Register your models here.
admin.site.register(PlaidItem)
admin.site.register(UserAccount)
admin.site.register(Transaction)
