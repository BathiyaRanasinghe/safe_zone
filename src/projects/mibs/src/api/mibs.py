'''
/mibs GET POST PUT DELETE endpoints
'''

from typing import Any, Dict, List, Tuple, Union
from flask import Blueprint, json, request
from flask.helpers import url_for
from dateutil.parser import parse as datetimeParse
from http import HTTPStatus

from lib.mibs.python.openapi.swagger_server.models import MessageInABottle, EmailRecipient
from lib.mibs.python.openapi.swagger_server.models.any_of_message_in_a_bottle_recipients_items \
    import AnyOfMessageInABottleRecipientsItems
from lib.mibs.python.openapi.swagger_server.models.sms_recipient import SmsRecipient
from lib.mibs.python.openapi.swagger_server.models.user_recipient import UserRecipient
from models import Message, EmailMessageRecipient, db

mibs_blueprint = Blueprint('mibs', __name__, url_prefix='/mibs')

TEMP_USER_ID = 'temp-user-id'

@mibs_blueprint.route('', methods=['GET'])
def get():
    '''
    TODO implement GET endpoint here
    '''
    return {
      'success': json.dumps(True),
      'message': 'Hello from GET /mibs',
    }


@mibs_blueprint.route('', methods=['POST'])
# TODO add authorization decorator
def post():
    '''
    /mibs POST endpoint. See openapi file.
    '''

    def validate() -> Tuple[bool, Tuple[str, HTTPStatus]]:
        if not request.is_json:
            return False, ('Request is not JSON', HTTPStatus.BAD_REQUEST)

        body = request.get_json()
        if not 'message' in body:
            return False, ('"message" missing from request body', HTTPStatus.BAD_REQUEST)

        if not 'recipients' in body:
            return False, ('"recipients" missing from request body', HTTPStatus.BAD_REQUEST)

        email_recipients, sms_recipients, user_recipients, unknown_recipients = \
            _parse_recipients(body['recipients'])
        if len(unknown_recipients) > 0:
            return False, (f'Unknown recipient types: {json.dumps(unknown_recipients)}', \
                HTTPStatus.BAD_REQUEST)

        if len(email_recipients + sms_recipients + user_recipients) <= 0:
            return False, ('Must have atleast 1 recipient', HTTPStatus.BAD_REQUEST)

        if not 'sendTime' in body:
            return False, ('"sendTime" missing from request body', HTTPStatus.BAD_REQUEST)

        try:
            datetimeParse(body['sendTime'])
        except ValueError:
            return False, ('"sendTime" is not an ISO-8601 UTC date time string', \
                HTTPStatus.BAD_REQUEST)

        return True, (None, None)

    assert request is not None

    is_valid_request, error_response = validate()

    if not is_valid_request:
        return error_response

    # Note: the request recipients is not converted to a
    # AnyOfMessageInABottleRecipients and is instead just a dict
    mib = MessageInABottle.from_dict(request.get_json())
    email_recipients, *_ = _parse_recipients(mib.recipients)

    message = Message(
        user_id=TEMP_USER_ID,
        message=mib.message,
        send_time=mib.send_time,
        email_recipients=[
            EmailMessageRecipient(email=email_recipient.email)
            for email_recipient in email_recipients
        ]
    )

    db.session.add(message)
    db.session.commit()

    return 'MessageInABottle was successfully created', HTTPStatus.OK, \
        {'Location': url_for('.get', messageId=message.message_id)}


def _parse_recipients(recipients: List[Union[AnyOfMessageInABottleRecipientsItems, \
    Dict[str, Any]]]) -> Tuple[EmailRecipient, SmsRecipient, UserRecipient, Dict[str, Any]]:
    '''
    Parse a list recipeints in to their respective categories.

    Preconditions:
        recipients is not None
        recipients is a list

    Postconditions:
        returns a tuple of (email_recipients, sms_recipients, user_recipients, unknown_recipients)
            where each element of the tuple is a list of recipients corresponding to that
            category
        Note: sms_recipients and user_recipients will always be empty lists and their entries
            will be in unknown_recipients since sms and user recipients are not implemented.
    '''

    assert recipients is not None
    assert isinstance(recipients, List)

    email_recipients = []
    sms_recipients = []
    user_recipients = []
    unknown_recipients = []
    for recipient in recipients:
        if 'email' in recipient:
            email_recipients.append(EmailRecipient.from_dict(recipient))
        else:
            unknown_recipients.append(recipient)

    return (email_recipients, sms_recipients, user_recipients, unknown_recipients)


@mibs_blueprint.route('', methods=['PUT'])
def put():
    '''
    TODO implement PUT endpoint here
    '''
    return {
      'success': json.dumps(True),
      'message': 'Hello from PUT /mibs',
    }


@mibs_blueprint.route('', methods=['DELETE'])
def delete():
    '''
    TODO implement DELETE endpoint here
    '''
    return {
      'success': json.dumps(True),
      'message': 'Hello from DELETE /mibs',
    }
