import io
import unittest
import json
from django.test import TestCase, Client
from django.db import connection
from LegacySite.models import Card, User

"""
Test Database Isolation: 
Each test in Django runs in isolation with a separate test database. 
This means that any data created, modified, or deleted in one test will not affect other tests. 
The test database is created at the start of the test run and destroyed at the end.
"""


class MyTest(TestCase):
    # TODO: READ THIS AND COMPLETE THIS FIRST BEFORE YOU RUN THE TESTS PROVIDED!
    # Django's test run with an empty database.
    # We can populate it with data by using a fixture.
    # Note that for the fixture to be populated correctly, you must complete migrations and imports!
    # You can create the fixture by running:
    #    mkdir LegacySite/fixtures
    #    python manage.py dumpdata LegacySite --indent=4> LegacySite/fixtures/testdata.json
    # You can read more about fixtures here:
    #    https://docs.djangoproject.com/en/4.0/topics/testing/tools/#fixture-loading
    # When you create your fixture, remember to uncomment the line where, fixtures = ["testdata.json"]
    #fixtures = ["testdata.json"]

    """
    Setup Method: 
    In the setUp method, you're creating a new Client instance. 
    This instance is unique for each test method and maintains its own session. 
    Therefore, when you register and log in a user within a test method, 
    the session is specific to this Client instance and that test method.
    
    setUp() is called everytime before a function starting with 'test_' is executed.
    Note that to be visible to `python3 manage.py test`, the python file must start with 'test'
    """
    def setUp(self):
        # Register and login our user to correctly handle session
        self.client = Client()
        self.username, self.password = 'test', 'test'
        self.register_user(self.username, self.password)
        self.client.login(username=self.username, password=self.password)

    
    def test_xss_protection(self):
        response = self.client.get("/buy.html?director=<script>alert('hello')</script>")
        self.assertNotContains(response, "<script>alert('Hello')</script>")
    
    def test_xsrf(self):
        # Enable CSRF checks for the test client
        self.client = Client(enforce_csrf_checks=True)
        
        # Attempt to make a POST request to the /gift/0 endpoint without a CSRF token
        response = self.client.post('/gift/0', {'username': 'test', 'amount': '123456'})

        # Assert that the response status code indicates a forbidden error (403)
        self.assertEqual(response.status_code, 403, "XSRF attack should not be successful; expected Forbidden (403) response.")
        
        # Additional feedback to verify the outcome
        if response.status_code == 403:
            print("XSRF attack not successful! Forbidden error returned as expected.")



     
    def test_sqli(self):
        test_client = Client()

        # Perform login
        login_resp = test_client.login(username='test', password='test')

        with open("part1/sqli.gftcrd", "r") as fd:
            http_resp = test_client.post("/use.html", {'card_supplied': True, "card_fname": "test", "card_data": fd})

            self.assertNotContains(http_resp, "000000000000000000000000000078d2$18821d89de11ab18488fdc0a01f1ddf4d290e19"
                                              "8b0f80cd4974fc031dc2615a3")


    def test_cmdi(self):
        test_client = Client()

        # Perform login
        login_resp = test_client.login(username='test', password='test')

        with open("part1/cmdi.gftcrd", "r") as fd:
            try:
                http_resp = test_client.post("/use.html", {'card_supplied': True, "card_data": fd,
                                                           "card_fname": "bla.txt; touch hacked;"})

            except json.decoder.JSONDecodeError:
                pass
   


    def test_buy_and_use(self):
        client = Client()
        client.login(username='test', password='test')
        user = User.objects.get(username='test')
        response = client.post('/buy/4', {'amount': 1337})
        self.assertEqual(response.status_code, 200)
        # Get the card that was returned
        card = Card.objects.filter(user=user.pk).order_by('-id')[0]
        card_data = response.content
        response = client.post('/use.html',
                               {
                                   'card_supplied': 'True',
                                   'card_fname': 'Test',
                                   'card_data': io.BytesIO(card_data),
                               }
                               )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Card used!', response.content)
        self.assertTrue(Card.objects.get(pk=card.id).used)



    def register_user(self, username, password):
        endpoint = '/register'
        data = {'uname': username,
                'pword': password, 
                'pword2': password}
        self.client.post(path=endpoint, data=data)
        canLogin = self.client.login(username=username, password=password)
        self.assertTrue(canLogin)



