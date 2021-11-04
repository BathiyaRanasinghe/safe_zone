'''
/mibs endpoint unit tests
'''
import unittest


import re
from urllib.parse import urlparse, parse_qs
from dateutil.parser import parse as datetimeParse
from datetime import datetime
from api.mibs import mibs_blueprint, delete_mibs_for_user, TEMP_USER_ID
from models import Message, EmailMessageRecipient, db
from flask import Flask, request, json
from http import HTTPStatus

test_email = 'test@email.com'
test_user_id = 'temp-user-id'
test_other_user = 'other_user'
test_message_id = 1
test_message_id2 = 2


class TestMibsApi(unittest.TestCase):
    '''
    /mibs endpoint unit tests
    '''

    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        db.init_app(self.app)
        with self.app.app_context():
            db.create_all()
            db.engine.execute('PRAGMA foreign_keys=ON')
        self.app.register_blueprint(mibs_blueprint)

        self.client = self.app.test_client()

        self.test_message = {
            'message': 'test message',
            'recipients': [
                {
                    'email': 'test@email.com'
                    }
            ],
            'sendTime': '2021-10-27T23:22:19.911Z'
        }

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_post_not_json(self):
        '''
        Test POST /mibs when content type is not application/json
        '''
        response = self.client.post(
            '/mibs',
            content_type='application/x-www-form-urlencoded',
            json=self.test_message
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertEqual(response.data, b'Request is not JSON')

    def test_post_missing_message(self):
        '''
        Test POST /mibs when request body is missing field "message"
        '''
        self.test_message.pop('message')
        response = self.client.post(
            '/mibs',
            json=self.test_message
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertEqual(response.data, b'"message" missing from request body')

    def test_post_missing_recipients(self):
        '''
        Test POST /mibs when request body is missing field "recipients"
        '''
        self.test_message.pop('recipients')
        response = self.client.post(
            '/mibs',
            json=self.test_message
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertEqual(
            response.data, b'"recipients" missing from request body')

    def test_post_empty_recipients(self):
        '''
        Test POST /mibs when request body's recipients field is an empty array
        '''
        self.test_message['recipients'] = []
        response = self.client.post(
            '/mibs',
            json=self.test_message
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertEqual(response.data, b'Must have atleast 1 recipient')

    def test_post_invalid_recipients(self):
        '''
        Test POST /mibs when request body's recipients field container invalid recipients
        '''
        test_phone_number = 'testPhoneNumber'
        test_invalid = 'testInvalid'
        self.test_message['recipients'] = [
            {'email': test_email},
            {'phoneNumber': test_phone_number},
            {'userId': test_user_id},
            {'invalid': test_invalid},
        ]
        response = self.client.post(
            '/mibs',
            json=self.test_message
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertNotIn(test_email.encode(), response.data)
        self.assertIn(test_phone_number.encode(), response.data)
        self.assertIn(test_user_id.encode(), response.data)
        self.assertIn(test_invalid.encode(), response.data)

    def test_post_missing_send_time(self):
        '''
        Test POST /mibs when request body is missing field "sendTime"
        '''
        self.test_message.pop('sendTime')
        response = self.client.post(
            '/mibs',
            json=self.test_message
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertEqual(
            response.data, b'"sendTime" missing from request body')

    def test_post_invalid_send_time(self):
        '''
        Test POST /mibs when request body's sendTime field is not an ISO-8601 datetime
        '''
        self.test_message['sendTime'] = '2021-10-27T23:22:19.911Za'
        response = self.client.post(
            '/mibs',
            json=self.test_message
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertEqual(
            response.data, b'"sendTime" is not an ISO-8601 UTC date time string')

    def test_post_success_1_recipient(self):
        '''
        Test POST /mibs when request is successful with one recipient
        '''
        response = self.client.post(
            '/mibs',
            json=self.test_message
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn('Location', response.headers)
        self.assertRegex(response.headers['Location'], re.compile(
            r'^.*/mibs\?messageId=\d+$'))
        self.assertEqual(
            response.data, b'MessageInABottle was successfully created')

        message_id = int(
            parse_qs(urlparse(response.headers['Location']).query)['messageId'][0])

        with self.app.app_context():
            message = Message.query.get(message_id)

            self.assertEqual(message.message_id, message_id)
            self.assertEqual(message.user_id, TEMP_USER_ID)
            self.assertEqual(message.message, self.test_message['message'])
            self.assertFalse(message.sent)
            self.assertIsNone(message.last_sent_time)
            self.assertEqual(message.send_time,
                             datetimeParse(self.test_message['sendTime']).replace(tzinfo=None))

            self.assertFalse(message.sent)
            self.assertEqual(len(message.email_recipients), 1)
            self.assertEqual(message.email_recipients[0].email,
                             self.test_message['recipients'][0]['email'])
            self.assertFalse(message.email_recipients[0].sent)
            self.assertIsNone(message.email_recipients[0].send_attempt_time)

    def test_post_success_many_recipients(self):
        '''
        Test POST /mibs when request is successful with more than one recipient
        '''
        self.test_message['recipients'] = [
            {'email': 'test1@email.com'},
            {'email': 'test2@email.com'}
        ]
        response = self.client.post(
            '/mibs',
            json=self.test_message
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)

        message_id = int(
            parse_qs(urlparse(response.headers['Location']).query)['messageId'][0])

        with self.app.app_context():
            message = Message.query.get(message_id)

            self.assertEqual(len(message.email_recipients), 2)
            self.assertEqual(message.email_recipients[0].email,
                             self.test_message['recipients'][0]['email'])
            self.assertFalse(message.email_recipients[0].sent)
            self.assertEqual(message.email_recipients[1].email,
                             self.test_message['recipients'][1]['email'])
            self.assertFalse(message.email_recipients[1].sent)

    def test_delete_mibs_for_user_all_no_mibs(self):
        '''
        Test delete_mibs_for_user when its used to delete all mibs when the user has no mibs
        '''
        with self.app.app_context():
            self.assertFalse(delete_mibs_for_user(test_user_id, None))
            self.assertEqual(None, Message.query.get(test_message_id))

    def test_delete_mibs_for_user_all_no_mibs_but_another_user_has_a_mib(self):
        '''
        Test delete_mibs_for_user when its used to delete all mibs when the user has no mibs
        but another user has a mib
        '''
        self.create_message(user_id=test_other_user)
        with self.app.app_context():
            self.assertFalse(delete_mibs_for_user(test_user_id, None))
            self.assertNotEqual(None, Message.query.get(test_message_id))

    def test_delete_mibs_for_user_all_one_mib(self):
        '''
        Test delete_mibs_for_user when its used to delete all mibs when the user has one mib
        '''
        self.create_message()
        with self.app.app_context():
            self.assertTrue(delete_mibs_for_user(test_user_id, None))
            self.assertEqual(None, Message.query.get(test_message_id))

    def test_delete_mibs_for_user_all_two_mibs(self):
        '''
        Test delete_mibs_for_user when its used to delete all mibs when the user has two mibs
        '''
        self.create_message()
        self.create_message(message_id=test_message_id2)
        with self.app.app_context():
            self.assertTrue(delete_mibs_for_user(test_user_id, None))
            self.assertEqual(None, Message.query.get(test_message_id))
            self.assertEqual(None, Message.query.get(test_message_id2))

    def test_delete_mibs_for_user_specific_no_mibs(self):
        '''
        Test delete_mibs_for_user when its used to delete a single mib when the user has no mibs
        '''
        with self.app.app_context():
            self.assertFalse(delete_mibs_for_user(
                test_user_id, test_message_id))
            self.assertEqual(None, Message.query.get(test_message_id))

    def test_delete_mibs_for_user__specific_no_mibs_but_another_user_has_a_mib(self):
        '''
        Test delete_mibs_for_user when its used to delete a single mib when the user has no mibs
        but another user has a mib
        '''
        self.create_message(user_id=test_other_user)
        with self.app.app_context():
            self.assertFalse(delete_mibs_for_user(
                test_user_id, test_message_id))
            self.assertNotEqual(None, Message.query.get(test_message_id))

    def test_delete_mibs_for_user_specific_one_mib(self):
        '''
        Test delete_mibs_for_user when its used to delete a single mib when the user has one mib
        '''
        self.create_message()
        with self.app.app_context():
            self.assertTrue(delete_mibs_for_user(
                test_user_id, test_message_id))
            self.assertEqual(None, Message.query.get(test_message_id))

    def test_delete_mibs_for_user_specific_two_mibs(self):
        '''
        Test delete_mibs_for_user when its used to delete a single mib when the user has two mibs
        '''
        self.create_message()
        self.create_message(message_id=test_message_id2)
        with self.app.app_context():
            self.assertTrue(delete_mibs_for_user(
                test_user_id, test_message_id))
            self.assertEqual(None, Message.query.get(test_message_id))
            self.assertNotEqual(None, Message.query.get(test_message_id2))

    def test_delete_all_no_mibs(self):
        '''
        Test DELETE /mibs to delete all mibs when user has no mibs
        '''
        with self.app.app_context():
            response = self.client.delete('/mibs')
        self.assertEqual(HTTPStatus.NOT_FOUND, response.status_code)
        self.assertEqual('Failed to delete all mibs: User does not have any mibs',
                         response.get_data(as_text=True))
        self.assertEqual(0, self.get_num_user_messages())

    def test_delete_all_no_mibs_but_another_user_has_a_mib(self):
        '''
        Test DELETE /mibs to delete all mibs when user has no mibs but another user has a mib
        '''
        self.create_message(user_id=test_other_user)
        with self.app.app_context():
            response = self.client.delete('/mibs')
        self.assertEqual(HTTPStatus.NOT_FOUND, response.status_code)
        self.assertEqual('Failed to delete all mibs: User does not have any mibs',
                         response.get_data(as_text=True))
        self.assertEqual(0, self.get_num_user_messages())
        self.assertEqual(1, self.get_num_user_messages(test_other_user))

    def test_delete_all_one_mib(self):
        '''
        Test DELETE /mibs to delete all mibs when user has one mib
        '''
        self.create_message()
        with self.app.app_context():
            response = self.client.delete('/mibs')
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertEqual('Successfully deleted all mibs',
                         response.get_data(as_text=True))
        self.assertEqual(0, self.get_num_user_messages())

    def test_delete_all_two_mibs(self):
        '''
        Test DELETE /mibs to delete all mibs when user has two mibs
        '''
        self.create_message()
        self.create_message(message_id=test_message_id2)
        with self.app.app_context():
            response = self.client.delete('/mibs')
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertEqual('Successfully deleted all mibs',
                         response.get_data(as_text=True))
        self.assertEqual(0, self.get_num_user_messages())

    def test_delete_specific_no_mibs(self):
        '''
        Test DELETE /mibs to delete a specific mib when user has no mibs
        '''
        with self.app.app_context():
            response = self.client.delete(f'/mibs?messageId={test_message_id}')
        self.assertEqual(HTTPStatus.NOT_FOUND, response.status_code)
        self.assertEqual('Failed to delete mib with message id 1',
                         response.get_data(as_text=True))
        self.assertEqual(0, self.get_num_user_messages())

    def test_delete_specific_no_mibs_but_another_user_has_a_mib(self):
        '''
        Test DELETE /mibs to delete a specific mib when user has no mibs but another user has a
        mib
        '''
        self.create_message(user_id=test_other_user)
        with self.app.app_context():
            response = self.client.delete(f'/mibs?messageId={test_message_id}')
        self.assertEqual(HTTPStatus.NOT_FOUND, response.status_code)
        self.assertEqual('Failed to delete mib with message id 1',
                         response.get_data(as_text=True))
        self.assertEqual(0, self.get_num_user_messages())
        self.assertEqual(1, self.get_num_user_messages(test_other_user))

    def test_delete_specific_mib_when_user_has_one_mib(self):
        '''
        Test DELETE /mibs to delete a specific mib when user has one mib
        '''
        self.create_message()
        with self.app.app_context():
            response = self.client.delete(f'/mibs?messageId={test_message_id}')
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertEqual('Successfully deleted mib with message id 1',
                         response.get_data(as_text=True))
        self.assertEqual(0, self.get_num_user_messages())

    def test_delete_specific_mib_when_user_has_two_mibs(self):
        '''
        Test DELETE /mibs to delete a specific mib when user has two mibs
        '''
        self.create_message()
        self.create_message(message_id=2)
        with self.app.app_context():
            response = self.client.delete(f'/mibs?messageId={test_message_id}')
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertEqual('Successfully deleted mib with message id 1',
                         response.get_data(as_text=True))
        self.assertEqual(1, self.get_num_user_messages())

    def test_delete_mib_also_deletes_email_recipients(self):
        '''
        Test when deleting a mib, that any email recipients associated with the message are also
        automatically deleted
        '''
        self.create_message()
        with self.app.app_context():
            self.create_email_recipient()
            self.create_email_recipient(message_send_request_id=2)
            delete_mibs_for_user(test_user_id, test_message_id)
            self.assertEqual(None, EmailMessageRecipient.query.get(1))
            self.assertEqual(None, EmailMessageRecipient.query.get(2))

    def test_no_mibs_exist_id(self):
        """
        mibs-GET
        Trying to retrieve a mibs with a given messageId on an empty database
        Expected outcome: None is returned with NOT_FOUND response
        """
        response = self.client.get("/mibs", json={"messageId": 1})
        status = response.status_code
        data = response.get_json()
        self.assertEqual(data, [])
        self.assertEqual(status, HTTPStatus.NOT_FOUND)

    def test_no_mibs_exist_no_id(self):
        """
        mibs-GET
        Trying to retrieve mibs on an empty database without giving a messageId
        Expected outcome: None is returned with OK response
        """
        response = self.client.get("/mibs", json={"messageId": None})
        status = response.status_code
        data = response.get_json()
        self.assertEqual(data, [])
        self.assertEqual(status, HTTPStatus.OK)

    def test_request_with_nonexistant_id_(self):
        """
        mibs-GET
        Searching for MIB with a messageId that does not exist
        Expected outcome: an empty list is returned with a NOT_FOUND
        response
        """
        self.populate_messages()
        response = self.client.get("/mibs", json={"messageId": 100})
        status = response.status_code
        data = response.get_json()
        self.assertEqual(data, [])
        self.assertEqual(status, HTTPStatus.NOT_FOUND)

    def test_get_mib_with_valid_id(self):
        """
        mibs-GET
        Searching for a MIB with a valid messageId
        Expected outcome: the MIB with the corresponding messageId is returned with
        an OKAY response
        """
        self.populate_messages()
        response = self.client.get("/mibs", json={"messageId": 1})
        status = response.status_code
        data = response.get_json()
        self.assertNotEqual(data, [])
        self.assertEqual(data[0]["message_id"], 1)
        self.assertEqual(status, HTTPStatus.OK)

    def test_no_given_message_id(self):
        """
        mibs-GET
        Making request with no given messageId
        Expected outcome: all MIBs for the user are returned with an OKAY response
        """
        self.populate_messages()
        response = self.client.get("/mibs", json={"messageId": None})
        status = response.status_code
        data = response.get_json()
        self.assertIsNotNone(data)
        # user should have 5 messages
        self.assertEqual(len(data), 5)
        self.assertEqual(status, HTTPStatus.OK)

    # def not_authorized(self):
    #     """
    #     mibs-GET
    #     Making a request from an unauthorized user
    #     Expected outcome: no Mibs are returned with an UNAUTHORIZED response
    #     """
    #     pass

    def create_email_recipient(self,
                               message_send_request_id=1,
                               message_id=test_message_id,
                               email=test_email):
        '''
        Helper function to create and insert a email recipient in the database
        '''
        with self.app.app_context():
            email_recipient = EmailMessageRecipient(message_send_request_id=message_send_request_id,
                                                    message_id=message_id,
                                                    email=email)
            db.session.add(email_recipient)
            db.session.commit()

    def create_message(self,
                       message_id=test_message_id,
                       user_id=test_user_id,
                       message='test',
                       send_time=datetime.now()):
        '''
        Helper function to create and insert a message in the database
        '''
        with self.app.app_context():
            new_message = Message(message_id=message_id,
                                  user_id=user_id,
                                  message=message,
                                  send_time=send_time)
            db.session.add(new_message)
            db.session.commit()

    def get_num_user_messages(self, user_id=test_user_id):
        '''
        Helper function to get the number of messages a user has in the database
        '''
        with self.app.app_context():
            return db.session.query(Message).filter(Message.user_id == user_id).count()

    def populate_messages(self):
        """
        Fills database with messages
        """
        # mibs to populate the db
        filler_mibs = [
            {"message_id": 1, "user_id": TEMP_USER_ID,
                "message": "This was my first mibs message!",
                "send_time": datetime.now()},
            {"message_id": 2, "user_id": TEMP_USER_ID,
                "message": "This was my second mibs message!",
                "send_time": datetime.now()},
            {"message_id": 3, "user_id": "some id",
                "message": "This is someone else's message!",
                "send_time": datetime.now()},
            {"message_id": 4, "user_id": "a third id",
                "message": "There are more people making messages!",
                "send_time": datetime.now()},
            {"message_id": 5, "user_id": TEMP_USER_ID,
                "message": "This is actually my third message (ignore the 5)!",
                "send_time": datetime.now()},
            {"message_id": 6, "user_id": TEMP_USER_ID,
                "message": "I have a lot of messages!",
                "send_time": datetime.now()},
            {"message_id": 7, "user_id": "a third id",
                "message": "Felt like I needed another message!",
                "send_time": datetime.now()},
            {"message_id": 8, "user_id": "some id",
                "message": "Me too!",
                "send_time": datetime.now()},
            {"message_id": 9, "user_id": TEMP_USER_ID,
                "message": "We are almost up to ten mibs in the db!",
                "send_time": datetime.now()}
        ]
        with self.app.app_context():
            for i in range(len(filler_mibs)):
                db.session.add(Message(message_id=filler_mibs[i]["message_id"],
                                       user_id=filler_mibs[i]["user_id"],
                                       message=filler_mibs[i]["message"],
                                       send_time=filler_mibs[i]["send_time"]))
            db.session.commit()


if __name__ == '__main__':
    unittest.main()
