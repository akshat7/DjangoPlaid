from celery import shared_task
import datetime
import os
from .models import UserAccount, PlaidItem, Transaction

from plaid import Client


os.environ['PLAID_CLIENT_ID'] = '5fe70a6fdf1def0013986f26'
os.environ['PLAID_SECRET'] = '6d09259b55bd88f1bf7a9349653f17'
os.environ['PLAID_PRODUCTS'] = 'transactions'
os.environ['PLAID_COUNTRY_CODES'] = 'US'
os.environ['PLAID_ENV'] = 'sandbox'


plaid_client_id = os.getenv('PLAID_CLIENT_ID')
plaid_public_key = os.getenv('PLAID_PUBLIC_KEY')
plaid_secret = os.getenv('PLAID_SECRET')
plaid_environment = os.getenv('PLAID_ENV', 'sandbox')


def get_plaid_client():
    print("Getting Plaid Client")
    return Client(client_id=plaid_client_id,
                  secret=plaid_secret,
                  environment=plaid_environment)


@shared_task
def fetch_transactions_from_plaid(access_token, item_id=None, new_transactions=500):
    client = get_plaid_client()
    # access_token = PlaidItem.objects.filter(item_id=item_id)[0].access_token

    # transactions of two years i.e. 730 days
    start_date = '{:%Y-%m-%d}'.format(
        datetime.datetime.now() + datetime.timedelta(-730))
    end_date = '{:%Y-%m-%d}'.format(datetime.datetime.now())
    print("Requesting Transactions from Plaid")
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

    print("Storing Account Details in DB")
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

    print("Storing Transaction Details in DB")

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
