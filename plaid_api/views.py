from django.shortcuts import render

# Create your views here.
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .models import PlaidItem, UserAccount, Transaction
from .tasks import fetch_transactions_from_plaid, get_plaid_client
from plaid import errors
import datetime
import os


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
            ]
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

        fetch_transactions_from_plaid.delay(access_token)

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
def get_transaction_from_db(request):
    client = get_plaid_client()
    item = PlaidItem.objects.filter(user=request.user)
    if item.count() > 0:
        access_token = item.values('access_token')[0]['access_token']

        start_date = '{:%Y-%m-%d}'.format(
            datetime.datetime.now() + datetime.timedelta(-730))
        end_date = '{:%Y-%m-%d}'.format(datetime.datetime.now())

        try:
            transactions_response = client.Transactions.get(
                access_token, start_date, end_date)
        except errors.PlaidError as e:
            return HttpResponse("HTTP_400_BAD_REQUEST")

        return JsonResponse(transactions_response['transactions'], safe=False)
    else:
        return HttpResponse("No Data Exists for the User")


@login_required(login_url='/login/')
def get_account_info(request):
    client = get_plaid_client()
    item = PlaidItem.objects.filter(user=request.user)
    if item.count() > 0:
        access_token = item.values('access_token')[0]['access_token']
        try:
            accounts_response = client.Accounts.get(access_token)
        except errors.PlaidError as e:
            return HttpResponse("HTTP_400_BAD_REQUEST")

        return JsonResponse(accounts_response)
    else:
        return HttpResponse("No Data Exists for the User")


def fetch_transactions_from_plaid(access_token, item_id=None, new_transactions=500):
    client = get_plaid_client()
    # access_token = PlaidItem.objects.filter(item_id=item_id)[0].access_token

    # transactions of two years i.e. 730 days
    start_date = '{:%Y-%m-%d}'.format(
        datetime.datetime.now() + datetime.timedelta(-730))
    end_date = '{:%Y-%m-%d}'.format(datetime.datetime.now())

    transactions_response = client.Transactions.get(
        access_token, start_date, end_date, {
            'count': new_transactions,
        })

    if item_id is None:
        item_id = transactions_response['item']['item_id']

    items = PlaidItem.objects.filter(item_id=item_id)
    print(items)
    item = items[0]

    accounts = transactions_response['accounts']
    transactions = transactions_response['transactions']

    for account in accounts:
        account_list = UserAccount.objects.filter(
            account_id=account['account_id'])
        if account_list.count() > 0:
            for a in account_list:
                a.balance_available = account['balances']['available']
                a.balance_current = account['balances']['current']
                a.save()

        else:
            account_obj = UserAccount.objects.create(
                item=item,
                account_id=account['account_id'],
                balance_available=account['balances']['available'],
                balance_current=account['balances']['current'])

            account_obj.save()

    transaction_list = Transaction.objects.filter(
        account__item=item).order_by('-date')
    transaction_list_count = transaction_list.count()
    index = 0
    for transaction in transactions:
        if transaction_list_count > 0 and transaction['transaction_id'] == transaction_list[index].transaction_id:
            transaction_list[index].amount = transaction['amount']
            transaction_list[index].pending = transaction['pending']
            transaction_list[index].save()
            index += 1

        else:
            account_ = UserAccount.objects.filter(
                account_id=transaction['account_id'])[0]

            transaction_obj = Transaction.objects.create(
                transaction_id=transaction['transaction_id'],
                account=account_,
                amount=transaction['amount'],
                date=transaction['date'],
                name=transaction['name'],
                pending=transaction['pending'])

            transaction_obj.save()
