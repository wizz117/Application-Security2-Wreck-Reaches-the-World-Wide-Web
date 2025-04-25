import json
import re

from django.db.utils import IntegrityError
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.http import HttpResponseBadRequest
from LegacySite.models import User, Product, Card
from . import extras
from django.views.decorators.csrf import csrf_protect as csrf_protect
from django.contrib.auth import login, authenticate, logout
from django.core.exceptions import ObjectDoesNotExist
from html import escape

import os, tempfile

SALT_LEN = 16

# Create your views here.
# Landing page. Nav bar, most recently bought cards, etc.
def index(request): 
    context= {'user': request.user}
    return render(request, "index.html", context)

# Register for the service.
def register_view(request):
    if request.method == 'GET':
        return render(request, "register.html", {'method':'GET'})
    else:
        context = {'method':'POST'}
        uname = request.POST.get('uname', None)
        pword = request.POST.get('pword', None)
        pword2 = request.POST.get('pword2', None)
        assert (None not in [uname, pword, pword2])
        if pword != pword2:
            context["success"] = False
            return render(request, "register.html", context)
        salt = extras.generate_salt(SALT_LEN)
        hashed_pword = extras.hash_pword(salt, pword)
        hashed_pword = salt.decode('utf-8') + '$' + hashed_pword
        u = User(username=uname, password=hashed_pword)
        u.save()
        return redirect("index.html")


# Log into the service.
def login_view(request):
    if request.method == "GET":
        return render(request, "login.html", {'method':'GET', 'failed':False})
    else:
        context = {'method':'POST'}
        uname = request.POST.get('uname', None)
        pword = request.POST.get('pword', None)
        assert (None not in [uname, pword])
        user = authenticate(username=uname, password=pword)
        if user is not None:
            context['failed'] = False
            login(request, user)
            print("Logged in user")
        else:
            context['failed'] = True
            return render(request, "login.html", context)
        return redirect("index.html")

# Log out of the service.
def logout_view(request):
    if request.user.is_authenticated:
        logout(request)
    return redirect("index.html")

def buy_card_view(request, prod_num=0):
    if request.method == 'GET':
        context = {"prod_num" : prod_num}
        director = request.GET.get('director', None)
        if director is not None:
            # KG: Wait, what is this used for? Need to check the template.
            #my comments: Escaping HTML via HTML encoding and not trusting the user as well as the framework
            context['director'] = escape(director)
        if prod_num != 0:
            try:
                prod = Product.objects.get(product_id=prod_num) 
            except:
                return HttpResponse("ERROR: 404 Not Found.")
        else:
            try:
                prod = Product.objects.get(product_id=1) 
            except:
                return HttpResponse("ERROR: 404 Not Found.")
        context['prod_name'] = prod.product_name
        context['prod_path'] = prod.product_image_path
        context['price'] = prod.recommended_price
        context['description'] = prod.description
        return render(request, "item-single.html", context)
    elif request.method == 'POST':
        if prod_num == 0:
            prod_num = 1
        num_cards = len(Card.objects.filter(user=request.user))
        # Generate a card here, based on amount sent. Need binary for this.
        card_file_path = os.path.join(tempfile.gettempdir(), f"addedcard_{request.user.id}_{num_cards + 1}.gftcrd")
        card_file_name = "newcard.gftcrd"
        # Use binary to write card here.
        # Create card record with data.
        # For now, until we get binary, write random data.
        prod = Product.objects.get(product_id=prod_num)
        amount = request.POST.get('amount', None)
        if amount is None or amount == '':
            amount = prod.recommended_price
        extras.write_card_data(card_file_path, prod, amount, request.user)
        card_file = open(card_file_path, 'rb')
        card = Card(data=card_file.read(), product=prod, amount=amount, fp=card_file_path, user=request.user)
        card.save()
        card_file.seek(0)
        response = HttpResponse(card_file, content_type="application/octet-stream")
        response['Content-Disposition'] = f"attachment; filename={card_file_name}"
        return response
        #return render(request, "item-single.html", {})
    else:
        return redirect("/buy/1")


# Added the csrf protect to enable the csrf protection for the gift_card_view()
@csrf_protect
# KG: What stops an attacker from making me buy a card for him?
def gift_card_view(request, prod_num=0):
    context = {"prod_num": prod_num}
    if request.method == "GET" and 'username' not in request.GET:
        if not request.user.is_authenticated:
            return redirect("/login.html")
        # my comments: Commented this as this line is not required.
        # request.GET.get('director', None)
        context['user'] = None
        director = request.GET.get('director', None)
        if director is not None:
           
            # '''my comments: Escaping HTML via HTML encoding and not trusting the user as well as the framework 
            context['director'] = escape(director)
        if prod_num != 0:
            try:
                prod = Product.objects.get(product_id=prod_num) 
            except:
                return HttpResponse("ERROR: 404 Not Found.")
        else:
            try:
                prod = Product.objects.get(product_id=1) 
            except:
                return HttpResponse("ERROR: 404 Not Found.")
        context['prod_name'] = prod.product_name
        context['prod_path'] = prod.product_image_path
        context['price'] = prod.recommended_price
        context['description'] = prod.description
        return render(request, "gift.html", context)
    # Hack: older partner sites only support GET, so special case this.

   
    # my comments: Removing the OR condition so that Get requests should not be used to modify the data.
    elif request.method == "POST":
        # \ or request.method == "GET" and 'username' in request.GET:

        if not request.user.is_authenticated:
            return redirect("/login.html")
        if prod_num == 0:
            prod_num = 1
        # Get vars from either post or get
       
        user = request.POST.get('username', None)  # \if request.method == "POST" else request.GET.get('username', None)
        amount = request.POST.get('amount', None)  # \if request.method == "POST" else request.GET.get('amount', None)
        if user is None:
            return HttpResponse("ERROR 404")
        try:
            user_account = User.objects.get(username=user)
        except:
            user_account = None
        if user_account is None:
            context['user'] = None
            return render(request, f"gift.html", context)
        context['user'] = user_account
        num_cards = len(Card.objects.filter(user=user_account))
        card_file_path = os.path.join(tempfile.gettempdir(), f"addedcard_{user_account.id}_{num_cards + 1}.gftcrd")
        #extras.write_card_data(card_file_path)
        prod = Product.objects.get(product_id=prod_num)
        if amount is None or amount == '':
            amount = prod.recommended_price
        extras.write_card_data(card_file_path, prod, amount, request.user)
        prod = Product.objects.get(product_id=prod_num)
        card_file = open(card_file_path, 'rb')
        card_data = card_file.read()
        card = Card(data=card_data, product=prod,
                    amount=amount, fp=card_file_path, user=user_account)
        try:
            card.save()
        except IntegrityError:
            # for some reason after we gift a card through GET we get
            # an IntegrityError here, but the card is saved. So just
            # ignore it.
            pass
        card_file.close()
        return render(request, f"gift.html", context)

    else:
        return HttpResponseBadRequest("400: Bad Request")

def use_card_view(request):
    # Initialize context with no card found by default
    context = {'card_found': None}
    
    # Handle GET request
    if request.method == 'GET':
        # Redirect to login if the user is not authenticated
        if not request.user.is_authenticated:
            return redirect("login.html")
        
        # Try to retrieve unused cards for the user, or set to None if no cards exist
        try:
            user_cards = Card.objects.filter(user=request.user, used=False)
        except ObjectDoesNotExist:
            user_cards = None
        
        # Update context with card list and no specific card selected
        context['card_list'] = user_cards
        context['card'] = None
        return render(request, 'use-card.html', context)
    
    # Handle POST request when a card is supplied
    elif request.method == "POST" and request.POST.get('card_supplied', False):
        context['card_list'] = None  # No card list needed in this context

        # Get the uploaded card data file and the card filename from the POST request
        card_file_data = request.FILES['card_data']
        card_filename = request.POST.get('card_fname', None)
        
        # Sanitize card filename to ensure it has no special characters
        card_filename = re.sub('[^A-Za-z0-9]', '', card_filename)
        
        # Determine the file path for the card based on the filename and user ID
        if not card_filename:
            card_file_path = os.path.join(tempfile.gettempdir(), f'newcard_{request.user.id}_parser.gftcrd')
        else:
            card_file_path = os.path.join(tempfile.gettempdir(), f'{card_filename}_{request.user.id}_parser.gftcrd')
        
        # Parse the card data and read from the uploaded file
        card_data = extras.parse_card_data(card_file_data.read(), card_file_path)
        
        # Extract the signature from the parsed card data to identify the card uniquely
        signature = json.loads(card_data)['records'][0]['signature']
        
        # Retrieve user cards from the database
        card_matches = []
        user_cards = Card.objects.raw('select id, count(*) as count from LegacySite_card where LegacySite_card.user_id'
                                      ' = %s', [request.user.id])
        card_id = None
        
        # Iterate over all cards in the database and compare the signature
        for card in Card.objects.all():
            if not card.used:  # Process only unused cards
                card_data_str = card.data.decode("utf-8")
                card_data_json = json.loads(card_data_str)
                
                # Match the card based on signature
                if card_data_json["records"][0].get("signature", "") == signature:
                    card_matches.append(card_data_json)
                    card_id = card.id
        
        # Build a string listing matched cards for display if any matches were found
        matched_cards_str = ""
        for matched_card in card_matches:
            matched_cards_str += str(matched_card) + '\n'
        
        # If no matches are found, save the card as a new entry
        if not card_matches:
            # Use a new filename if specified or default to a new naming convention
            if card_filename:
                card_file_path = os.path.join(tempfile.gettempdir(), f'{card_filename}_{request.user.id}_{user_cards[0].count + 1}.gftcrd')
            else:
                card_file_path = os.path.join(tempfile.gettempdir(), f'newcard_{request.user.id}_{user_cards[0].count + 1}.gftcrd')
            
            # Write parsed card data to a temporary file
            with open(card_file_path, 'wb') as card_file:
                card_file.write(card_data)
            
            # Save the new card instance to the database
            card = Card(data=card_data, fp=card_file_path, user=request.user, used=True)
        else:
            # If matched cards were found, update context with found card info
            context['card_found'] = matched_cards_str
            
            # Mark the matched card as used and save
            try:
                card = Card.objects.get(id=card_id)
                card.used = True
                card.save()
            except ObjectDoesNotExist:
                print("No card found with data =", card_data)
                card = None
        
        # Set context card and render the template
        context['card'] = card
        return render(request, "use-card.html", context)
    
    # Handle POST request without specific card supplied
    elif request.method == "POST":
        # Retrieve the card based on provided card_id and mark it as used
        card = Card.objects.get(id=request.POST.get('card_id', None))
        card.used = True
        card.save()
        
        # Update context with the selected card and list of unused cards
        context['card'] = card
        try:
            user_cards = Card.objects.filter(user=request.user, used=False)
        except ObjectDoesNotExist:
            user_cards = None
        context['card_list'] = user_cards
        return render(request, "use-card.html", context)
    
    # Return a 404 error for unsupported requests
    return HttpResponse("Error 404: Internal Server Error")
