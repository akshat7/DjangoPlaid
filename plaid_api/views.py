from django.shortcuts import render

# Create your views here.
import os
import datetime
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from rest_framework.response import Response
from plaid import errors
from .models import PlaidItem, UserAccount, Transaction
from .tasks import fetch_transactions_from_plaid, get_plaid_client, delete_transactions
from .serializers import TransactionSerializer


def signup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)
            login(request, user)
            return render(request, 'index.html')
    else:
        form = UserCreationForm()
    return render(request, 'signup.html', {'form': form})


@login_required(login_url='/login/')
def home(request):
    return render(request, 'index.html')


@login_required(login_url='/login/')
def create_link_token(request):

    find_item = PlaidItem.objects.filter(user=request.user)
    print(find_item)

    if find_item.count() == 0:
        print("Fetching Link Token")
        client = get_plaid_client()

        res = client.Sandbox.public_token.create(
            'ins_109508',
            [
                'transactions'
            ],
            {
                "webhook":"http://c5f7faa175fe.ngrok.io/webhook/",
            }
        )

        publicToken = res['public_token']

        print("Fetching Access Token")
        res = client.Item.public_token.exchange(publicToken)

        access_token = res['access_token']
        item_id = res['item_id']
        # identity_data = client.Identity.get(access_token)
        # accounts = identity_data['accounts']

        print("Creating Plaid Item")
        plaid_item = PlaidItem.objects.create(
            access_token=access_token,
            item_id=item_id,
            user=request.user
        )

        plaid_item.save()

        print("Fetching initial Transactions and Account Details")

        # fetch_transactions_from_plaid.delay(access_token)
        fetch_transactions_from_plaid(access_token)
        print("Asyn task called, returning success now")
        return render(request, 'success.html')
    else:
        return HttpResponse("Access Token Already Exists. You can fetch your transactions.")


def get_access_token(client, public_token):
    print("Getting Access Token")
    exchange_response = client.Item.public_token.exchange(public_token)
    access_token = exchange_response['access_token']
    print(access_token)
    return access_token


@login_required(login_url='/login/')
def set_access_token(request):
    print("Setting Access Token")
    access_token = request.POST['access_token']
    print(access_token)

    return JsonResponse({'error': False})


@login_required(login_url='/login/')
@api_view()
def get_transaction_from_db(request):
    client = get_plaid_client()
    item = PlaidItem.objects.filter(user=request.user)
    print(item[0])
    
    print("Getting Accounts")
    accounts = UserAccount.objects.filter(item=item[0])
    print(accounts)
    
    print("Getting Transactions")
    transactions = []
    
    for account in accounts:
        transaction = Transaction.objects.filter(account=account)
        for t in transaction:
            transactions.append(t)
    print(len(transactions))
    print("Getting Serialized Data")
    transaction_serializer = TransactionSerializer(transactions, many=True)
    print(transaction_serializer.data)
    return Response(transaction_serializer.data)


@login_required(login_url='/login/')
@api_view()
def get_account_info(request):
    client = get_plaid_client()
    item = PlaidItem.objects.filter(user=request.user)
    if item.count() > 0:
        access_token = item.values('access_token')[0]['access_token']
        try:
            accounts_response = client.Accounts.get(access_token)
        except errors.PlaidError as e:
            return HttpResponse("HTTP_400_BAD_REQUEST")

        return Response(accounts_response)
    else:
        return HttpResponse("No Data Exists for the User")

@csrf_exempt
def webhook(request):
    request_data = request.POST
    print("Webhook received")
    print(request.POST)
    webhook_type = request_data.get('webhook_type')
    webhook_code = request_data.get('webhook_code')
    print(webhook_type)

    if webhook_type == 'TRANSACTIONS':
        item_id = request_data.get('item_id')
        if webhook_code == 'TRANSACTIONS_REMOVED':
            removed_transactions = request_data.get('removed_transactions')
            # delete_transactions.delay(item_id, removed_transactions)
            delete_transactions(item_id, removed_transactions)

        else:
            new_transactions = request_data.get('new_transactions')
            # fetch_transactions.delay(None, item_id, new_transactions)
            fetch_transactions(None, item_id, new_transactions)

    # return HttpResponse('Webhook received', status=status.HTTP_202_ACCEPTED)
    return HttpResponse('Webhook received')

@login_required(login_url='/login/')
def test_webhook(request):
    client = get_plaid_client()
    item = PlaidItem.objects.filter(user=request.user)
    access_token = item.values('access_token')[0]['access_token']
    print(access_token)
    # fire a DEFAULT_UPDATE webhook for an item
    client.Sandbox.item.fire_webhook(access_token, 'DEFAULT_UPDATE')
    return HttpResponse('Testing Webhook')