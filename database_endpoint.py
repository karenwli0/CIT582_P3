from flask import Flask, request, g
from flask_restful import Resource, Api
from sqlalchemy import create_engine, select, MetaData, Table
from flask import jsonify
import json
import eth_account
import algosdk
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import load_only
from datetime import datetime

from models import Base, Order, Log

engine = create_engine('sqlite:///orders.db')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)

app = Flask(__name__)


# These decorators allow you to use g.session to access the database inside the request code
@app.before_request
def create_session():
    g.session = scoped_session(
        DBSession)  # g is an "application global" https://flask.palletsprojects.com/en/1.1.x/api/#application-globals


@app.teardown_appcontext
def shutdown_session(response_or_exc):
    g.session.commit()
    g.session.remove()


"""
-------- Helper methods (feel free to add your own!) -------
"""


def log_message(d):
    # Takes input dictionary d and writes it to the Log table

    log_obj = Log(logtime=datetime.now(), message=d)
    g.session.add(log_obj)
    g.session.commit()


def add_to_order(sender_pk, receiver_pk, buy_currency, sell_currency, buy_amount, sell_amount, signature):
    order_obj = Order(sender_pk=sender_pk, receiver_pk=receiver_pk,
                      buy_currency=buy_currency, sell_currency=sell_currency,
                      buy_amount=buy_amount, sell_amount=sell_amount, signature=signature)
    # print(order_obj.sender_pk, "here")
    g.session.add(order_obj)
    g.session.commit()


"""
---------------- Endpoints ----------------
"""


@app.route('/trade', methods=['POST'])
def trade():
    if request.method == "POST":
        content = request.get_json(silent=True)
        print(f"content = {json.dumps(content)}")
        columns = ["sender_pk", "receiver_pk", "buy_currency", "sell_currency", "buy_amount", "sell_amount", "platform"]
        fields = ["sig", "payload"]
        error = False
        for field in fields:
            if not field in content.keys():
                print(f"{field} not received by Trade")
                print(json.dumps(content))
                log_message(content)
                return jsonify(False)

        error = False
        for column in columns:
            if not column in content['payload'].keys():
                print(f"{column} not received by Trade")
                error = True
        if error:
            print(json.dumps(content))
            log_message(content)
            return jsonify(False)

        # Your code here
        # Note that you can access the database session using g.session
        payload = content.get('payload')
        platform = payload.get('platform')
        sig = content.get('sig')
        pk = payload.get('sender_pk')

        result = False

        if platform == 'Ethereum':

            msg = json.dumps(payload)
            encoded_msg = eth_account.messages.encode_defunct(text=msg)

            if eth_account.Account.recover_message(encoded_msg, signature=sig) == pk:
                result = True

        if platform == 'Algorand':
            msg = json.dumps(payload)

            if algosdk.util.verify_bytes(msg.encode('utf-8'), sig, pk):
                result = True

        print(result)

        if not result:
            msg = json.dumps(payload)
            log_message(msg)

        if result:
            sender_pk = payload.get('sender_pk')
            receiver_pk = payload.get('receiver_pk')
            buy_currency = payload.get('buy_currency')
            sell_currency = payload.get('sell_currency')
            buy_amount = payload.get('buy_amount')
            sell_amount = payload.get('sell_amount')
            add_to_order(sender_pk, receiver_pk, buy_currency, sell_currency, buy_amount, sell_amount, sig)

@app.route('/order_book')
def order_book():
    # Your code here
    # Note that you can access the database session using g.session
    datalist = []
    for row in g.session.query(Order).all():

        temp = {'sender_pk': row.sender_pk, 'receiver_pk': row.receiver_pk, 'buy_currency': row.buy_currency,
                'sell_currency': row.sell_currency, 'buy_amount': row.buy_amount, 'sell_amount': row.sell_amount,
                'signature': row.signature}
        # print(temp)
        datalist.append(temp)
    result = {'data': datalist}
    # print(result)
    return jsonify(result)


if __name__ == '__main__':
    app.run(port='5002')
