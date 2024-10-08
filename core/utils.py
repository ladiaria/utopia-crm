from datetime import date, timedelta
import collections
from functools import wraps
import json
import requests
from requests.auth import HTTPBasicAuth
from requests.exceptions import ReadTimeout, RequestException
from typing import Literal
from html2text import html2text
import logging

from django.conf import settings
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.core.mail import mail_managers
from rest_framework.decorators import authentication_classes


logger = logging.getLogger(__name__)


def mailtrain_api_call(endpoint, method='get', data=None):
    try:
        assert getattr(settings, "MAILTRAIN_API_URL", None) and getattr(settings, "MAILTRAIN_API_KEY", None), \
            "Mailtrain API URL or API Key is not configured properly."
        url = f"{settings.MAILTRAIN_API_URL}{endpoint}"
        params = {'access_token': settings.MAILTRAIN_API_KEY}
        if method == 'get':
            response = requests.get(url, params=params)
        elif method == 'post':
            response = requests.post(url, params=params, data=data)
        response.raise_for_status()
        return response
    except (AssertionError, requests.RequestException) as e:
        logger.error(f"Mailtrain API error: {str(e)}")
        return None


def subscribe_email_to_mailtrain_list(email, mailtrain_list_id):
    if settings.DEBUG:
        logger.debug(f"Sending email {email} to list {mailtrain_list_id}")
    response = mailtrain_api_call(f'subscribe/{mailtrain_list_id}', method='post', data={'EMAIL': email})
    return response.json() if response else None


def unsubscribe_email_from_mailtrain_list(email, mailtrain_list_id):
    if settings.DEBUG:
        logger.debug(f"Unsubscribing email {email} from list {mailtrain_list_id}")
    response = mailtrain_api_call(f'unsubscribe/{mailtrain_list_id}', method='post', data={'EMAIL': email})
    return response.json() if response else None


def delete_email_from_mailtrain_list(email, mailtrain_list_id):
    if settings.DEBUG:
        logger.debug(f"Deleting email {email} from list {mailtrain_list_id}")
    response = mailtrain_api_call(f'delete/{mailtrain_list_id}', method='post', data={'EMAIL': email})
    return response.json() if response else None


def get_mailtrain_lists(email):
    response = mailtrain_api_call(f'lists/{email}')
    if response:
        return [mlist["cid"] for mlist in response.json()["data"] if mlist["status"] == 1]
    return []


def get_emails_from_mailtrain_list(mailtrain_list_id, status=None, limit=None):
    params = {}
    if limit:
        params['limit'] = limit
    response = mailtrain_api_call(f'subscriptions/{mailtrain_list_id}', data=params)
    if not response:
        return []

    data = response.json()
    return [
        subscription['email']
        for subscription in data['data']['subscriptions']
        if not status or subscription["status"] == status
    ]


def user_mailtrain_lists(email):
    response = mailtrain_api_call(f'lists/{email}')
    if not response:
        return []

    json_response = response.json()
    return [
        {'name': item.get('name'), 'status': item.get('status'), 'cid': item.get('cid')}
        for item in json_response["data"]
    ]


dnames = ('monday', 'tuesday', 'wednesday', 'thursday', 'friday')


def addMonth(d, n=1):
    """
    Add n+1 months to date then subtract 1 day. To get eom, last day of target month.
    """
    q, r = divmod(d.month + n, 12)
    eom = date(d.year + q, r + 1, 1) - timedelta(days=1)
    if d.month != (d + timedelta(days=1)).month or d.day >= eom.day:
        return eom
    return eom.replace(day=d.day)


def calc_price_from_products(products_with_copies, frequency, debug_id=""):
    """
    Returns the prices, we need the products already processed.
    """
    from core.models import Product, AdvancedDiscount

    total_price, discount_pct, frequency = 0, 0, int(frequency)

    percentage_discount, debug = None, getattr(settings, 'DEBUG_PRODUCTS', False)
    if debug and debug_id:
        debug_id += ": "
    all_list = products_with_copies.items()
    subscription_product_list, discount_product_list, other_product_list, advanced_discount_list = [], [], [], []

    # 1. partition the input by discount products / non discount products
    for product_id, copies in all_list:
        try:
            product = Product.objects.get(pk=int(product_id))
        except Product.DoesNotExist:
            pass
        else:
            if product.type in ('D', 'P', 'A'):
                discount_product_list.append(product)
            elif product.type == "S":
                subscription_product_list.append(product)
            elif product.type == "O":
                other_product_list.append(product)

    # 2. obtain 2 total cost amounts: affectable/non-affectable by discounts
    total_affectable, total_non_affectable = 0, 0
    for product in subscription_product_list:
        copies = int(products_with_copies[product.id])
        if debug:
            print(
                f"{debug_id}{product.name} {copies}x{'-' if product.type == 'D' else ''}"
                f"{product.price} = {'-' if product.type == 'D' else ''}{product.price * copies}"
            )
        # check first if this product is affected to any of the discounts
        affectable = False
        for discount_product in [d for d in discount_product_list if d.target_product == product]:
            affectable_delta = product.price * copies
            if discount_product.type == "D":
                affectable_delta -= discount_product.price * int(products_with_copies[discount_product.id])
            elif discount_product.type == "P":
                affectable_delta_discount = (affectable_delta * discount_product.price) / 100
                affectable_delta -= affectable_delta_discount
            total_affectable += affectable_delta
            discount_product_list.remove(discount_product)
            affectable = True
            break
        if not affectable:
            # not affected by discounts but the product price can be also "affectable" if has_implicit_discount
            product_delta = product.price * copies
            if product.has_implicit_discount:
                total_affectable += product_delta
            else:
                total_non_affectable += product_delta

    if debug:
        print(debug_id + "before3 affectable=%s, non-affectable=%s" % (total_affectable, total_non_affectable))

    # 3. iterate over discounts left
    for product in discount_product_list:
        if product.type == 'D':
            total_non_affectable -= product.price * int(products_with_copies[product.id])
        elif product.type == 'P':
            percentage_discount = product  # only one percentage discount product (the last one found in the list).
        elif product.type == 'A':
            advanced_discount_list.append(product)

    if debug:
        print(debug_id + "after3 affectable=%s, non-affectable=%s" % (total_affectable, total_non_affectable))

    # After calculating the prices of the product, we check out every product in the advanced_discount_list
    # TODO: this must be tested
    for discount_product in advanced_discount_list:
        try:
            advanced_discount = AdvancedDiscount.objects.get(discount_product=discount_product)
        except AdvancedDiscount.DoesNotExist:
            continue
        else:
            if advanced_discount.value_mode == 1:
                discounted_product_price = advanced_discount.value
            else:
                discounted_product_price = 0
                for product in advanced_discount.find_products.all():
                    if product.id in products_with_copies:
                        if product.type == 'S':
                            discounted_product_price += int(products_with_copies[product.id]) * product.price
                        else:
                            discounted_product_price -= int(products_with_copies[product.id]) * product.price
                discounted_product_price = (discounted_product_price * advanced_discount.value) / 100
            total_non_affectable -= discounted_product_price

    if debug:
        print(debug_id + "before_pd affectable=%s, non-affectable=%s" % (total_affectable, total_non_affectable))

    # After calculating the prices of S and D products, we need to calculate the one for P.
    if percentage_discount:
        total_non_affectable -= (total_non_affectable * percentage_discount.price) / 100

    if debug:
        print(debug_id + "after_pd affectable=%s, non-affectable=%s" % (total_affectable, total_non_affectable))

    # Then we multiply all this by the frequency
    total_price = float((total_affectable + total_non_affectable) * frequency)

    # Next step is determining if there's a discount for frequency.
    discount_pct = getattr(settings, 'DISCOUNT_%d_MONTHS' % frequency, 0)
    if discount_pct:
        total_price -= (total_price * discount_pct) / 100

    # Finally we add the price of the one-shot products since they're not affected by the frequency discount.
    for product in other_product_list:
        total_price += float(product.price)

    if debug:
        print(debug_id + "Total {}\n".format(total_price))

    return round(total_price)


def process_products(input_product_dict: dict) -> dict:
    """
    Takes products from a product list (for example from a subscription products list) and turns them into new products
    that are already bundled. These will be executed in order of priority, from smallest to greatest.

    Each of the products must be a tuple with product and copies.
    """
    from core.models import Product, PriceRule

    input_product_ids = list(input_product_dict.keys())
    input_products = Product.objects.filter(id__in=input_product_ids)
    input_products_count, output_dict, non_discount_added = input_products.count(), {}, 0

    for pricerule in PriceRule.objects.filter(active=True).order_by('priority'):
        exit_loop = False
        products_in_list_and_pool = []
        pool = pricerule.products_pool.all()
        not_pool = pricerule.products_not_pool.all()
        ignore_product_bundle = pricerule.ignore_product_bundle.all()

        if not_pool:
            for product in not_pool:
                if product in input_products or product.id in list(output_dict.keys()):
                    # If any of the products is in the list of input products and on the not_pool, we skip the rule
                    exit_loop = True
                    break

        if exit_loop:
            continue

        for bundle in ignore_product_bundle:
            if collections.Counter(list(input_products)) == collections.Counter(list(bundle.products.all())):
                exit_loop = True
                break

        if exit_loop:
            continue

        rm_after = []
        for input_product in input_products:
            if pricerule.wildcard_mode == "pool_or_any":
                if not input_product.has_implicit_discount:
                    if input_product.type in "DP" and input_product.target_product:
                        rm_after.append(input_product.target_product)
                    else:
                        products_in_list_and_pool.append(input_product)
            elif input_product in pool:
                products_in_list_and_pool.append(input_product)

        non_discount_added_ignore = 0
        for p in rm_after:
            try:
                products_in_list_and_pool.remove(p)
            except ValueError:
                # if found in output (added by previous rule), inc the ammount to substract
                if p.id in output_dict:
                    non_discount_added_ignore += 1

        list_and_pool_len, pr_res_prod = len(products_in_list_and_pool), pricerule.resulting_product
        if pricerule.wildcard_mode == "pool_and_any":
            # wildcard_mode "AND ANY": it means it has to be in the pool, and MUST NOT be the only product in the mix.
            if input_products_count > 1 and list_and_pool_len > 0:
                output_dict[pr_res_prod.id] = input_product_dict[input_product_ids[0]]
        else:
            if pricerule.wildcard_mode == "pool_or_any":
                # consider also non discount products that have been added to the output_dict by previous rules
                list_and_pool_len += non_discount_added - non_discount_added_ignore
            if (pricerule.amount_to_pick_condition == "eq" and list_and_pool_len == pricerule.amount_to_pick) or (
                pricerule.amount_to_pick_condition == "gt" and list_and_pool_len > pricerule.amount_to_pick
            ):

                if pricerule.mode == 1:
                    # We use the copies for any of the products, the first one for instance, they should all be the
                    # same since they're on the 'choose all products' mode.
                    output_dict[pr_res_prod.id] = input_product_dict[str(products_in_list_and_pool[0].id)]
                    # We're going to exclude the products that were not used here so they can be used by other rules.
                    for product in input_products:
                        if product in pool:
                            input_products = input_products.exclude(pk=product.id)
                    # Increment "non discount" counter if is the case
                    if pr_res_prod.type not in "DP" and not pr_res_prod.has_implicit_discount:
                        non_discount_added += 1
                elif pricerule.mode == 2:
                    # This is if we only need to change one product into another. WIP.
                    output_dict[pricerule.choose_one_product.id] = products_in_list_and_pool[0][1]
                    for product in input_products:
                        if product == pricerule.choose_one_product:
                            # We're only going to replace the chosen product from the mix.
                            input_products = input_products.exclude(pk=product.id)
                elif pricerule.mode == 3:
                    # We just add an extra product to the list. We're not going to remove them from input products.
                    # Again we take the copies from the first product on the list. This might be dangerous, and might
                    # need a different value. We might change it to 1.
                    output_dict[pr_res_prod.id] = input_product_dict[input_product_ids[0]]

    # In the end we will also add the remainder of the products that were not used to the output dictionary.
    # Note that this is useful to place the untargetted percentage discounts that came on input AFTER the untargetted
    # percentage discounts added by the rules, because the price calculation function will use only the LAST one found,
    # and as expected, the rules ones will not be applied.
    for product in input_products:
        output_dict[product.id] = input_product_dict[str(product.id)]
    return output_dict


def no_op_decorator(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


# Endpoints must be decorated with no auth classes if the deployment is under http basic auth, when no basic auth is
# set, the decorator is no_op_decorator, which does nothing and let the endpoint acts as if it was not decorated.
api_view_auth_decorator = (
    authentication_classes([]) if getattr(settings, 'ENV_HTTP_BASIC_AUTH', False) else no_op_decorator
)


def cms_rest_api_kwargs(api_key, data=None):
    http_basic_auth = settings.WEB_UPDATE_HTTP_BASIC_AUTH
    result = {
        "headers": {"X-Api-Key": api_key} if http_basic_auth else {'Authorization': 'Api-Key ' + api_key},
        "timeout": (5, 20),
    }
    if not getattr(settings, "WEB_UPDATE_USER_VERIFY_SSL", True):
        result["verify"] = False
    if data:
        result["data"] = data
    if http_basic_auth:
        result["auth"] = HTTPBasicAuth(*http_basic_auth)
    return result


def updatewebuser(cid, email, newemail, name="", last_name="", fields_values={}, method="PUT"):
    """
    Performs a PUT or a POST to the WEB CMS REST API to update or create the CMS models related to the contact.
    TODO: Document the usage of the fields_values parameter.
    """
    data = {
        "contact_id": cid,
        "name": name,
        "last_name": last_name,
        "email": email,
        "newemail": newemail,
        "fields": json.dumps(fields_values),
    }
    try:
        cms_rest_api_request("updatewebuser", settings.WEB_UPDATE_USER_URI, data, method)
    except Exception as e:
        if settings.DEBUG:
            print(f"ERROR: updatewebuser: {e}")


def cms_rest_api_request(api_name, api_uri, post_data, method="POST"):
    """
    Performs a request to the CMS REST API.
    @param api_name: Name of the function that is calling the API
    @param api_uri: URL of the endpoint.
    @param post_data: Request data to be sent.
    @param method: Http method to be used.
    """
    api_key = settings.LDSOCIAL_API_KEY
    if not (api_uri or api_key) or method not in ("POST", "PUT", "DELETE"):
        return "ERROR"
    try:
        if settings.DEBUG:
            print("DEBUG: %s to %s with method='%s', data='%s'" % (api_name, api_uri, method, post_data))

        if (
            settings.WEB_UPDATE_USER_ENABLED if method == "PUT" else (
                settings.WEB_CREATE_USER_ENABLED or api_uri in settings.WEB_CREATE_USER_POST_WHITELIST
            )
        ):
            r = getattr(requests, method.lower())(api_uri, **cms_rest_api_kwargs(api_key, post_data))
            if settings.DEBUG:
                html2text_content = html2text(r.content.decode()).strip()
                # TODO: can be improved splitting and stripping more unuseful info
                print(
                    "DEBUG: CMS api response content: " + html2text_content.split("## Request information")[0].strip()
                )
            r.raise_for_status()
            result = r.json()
            if settings.DEBUG:
                print(f"DEBUG: {api_name} {method} result: {result}")
            return result
        else:
            print(f"DEBUG: {api_name} {method} conditions to call CMS API not met")
    except ReadTimeout as rt:
        if settings.DEBUG:
            print(f"DEBUG: {api_name} {method} read timeout: {str(rt)}")
        return "TIMEOUT"
    except RequestException as req_ex:
        if settings.DEBUG:
            print(f"DEBUG: {api_name} {method} request error: {str(req_ex)}")
        return "ERROR"
    else:
        return {"msg": "OK"}


def validateEmailOnWeb(contact_id, email):
    return cms_rest_api_request(
        "validateEmailOnWeb", settings.WEB_EMAIL_CHECK_URI, {"contact_id": contact_id, "email": email}
    )


def manage_mailtrain_subscription(email: str, list_id: str, action: Literal["subscribe", "unsubscribe"]) -> dict:
    """
    Service function to add or remove an email from a Mailtrain list.
    """
    try:
        validate_email(email)
    except ValidationError:
        raise ValueError(f"{email} is not a valid email address.")  # Using ValueError for invalid input

    if action not in ["subscribe", "unsubscribe"]:
        raise ValueError("Invalid action specified.")  # Same here for invalid action

    if action == "subscribe":
        result = subscribe_email_to_mailtrain_list(email, list_id)
    else:  # 'unsubscribe' action
        result = delete_email_from_mailtrain_list(email, list_id)

    return result


def select_or_create_contact(email, name=None, phone=None, id_document=None):
    """
    Check if a contact exists in the CRM, if not, create it.

    Args:
        email (str): The email address of the contact.
        name (str): The name of the contact.
        phone (str): The phone number of the contact.
        id_document (str): The identification document of the contact.

    Returns the contact object.
    """
    from core.models import Contact
    contact_qs = Contact.objects.filter(email=email)
    if contact_qs.exists():
        contact_obj = contact_qs.first()
    else:
        contact_obj = Contact.objects.create(email=email, name=name, phone=phone, id_document=id_document)
    return contact_obj


def process_invoice_request(product_slugs, email, phone, name, id_document, payment_type):
    from core.models import Product
    """
    Handles the core logic for processing an invoice request by selecting or creating a contact, retrieving
    the specified products, and creating a one-time invoice.

    This function encapsulates the process of validating input data, handling contact selection or creation,
    and managing product retrieval before creating the invoice. It separates these steps from direct invoice
    creation to allow for better code reusability, error handling, and potential pre- or post-processing logic,
    such as logging, validation, or customization for different project requirements.

    Args:
        product_slugs (str): Comma-separated product slugs representing the items the user wants to purchase.
        email (str): The email address of the user making the purchase, typically received from the CMS.
        phone (str): The phone number of the user. If not provided, defaults to an empty string.
        name (str): The name of the user. If not provided, defaults to an empty string.
        payment_reference (str): A reference identifier for the payment transaction. This helps track payments.
        payment_type (str): The type of payment used (e.g., credit card, PayPal).

    Returns:
        dict: A dictionary containing the invoice ID and contact ID, which can be used for further processing
        or response.

    Raises:
        ValueError: If no products are found corresponding to the provided slugs.

    Why This Function is Separate:
    - Modularity: By separating this function from `add_single_invoice_with_products`, the logic for contact
      and product handling is modular, making the code easier to maintain and extend. This separation allows the
      function to be reused in different contexts where pre-processing of the invoice is needed before calling
      the actual invoice creation method.
    - Error Handling: The function includes input validation and error handling before the invoice is created,
      ensuring that all necessary data is present and valid. This makes it easier to manage exceptions specific
      to contact and product handling before attempting to create an invoice.
    - CMS Integration: The function is designed to work with a CMS that may not know if the CRM already has a
      contact for the provided email. Therefore, it is responsible for creating a new contact if one doesn't exist,
      ensuring seamless integration between the CMS and CRM.
    - Customization: This function can be customized or overridden in different contexts (e.g., different
      projects or environments) without affecting the core invoice creation logic. For example, additional steps
      can be added before or after the invoice creation based on specific business requirements.
    """
    contact_obj = select_or_create_contact(email, name, phone, id_document)
    product_objs = Product.objects.filter(slug__in=product_slugs.split(","))

    if not product_objs:
        raise ValueError("No se encontraron productos")

    invoice = contact_obj.add_single_invoice_with_products(product_objs, payment_type)
    for product in product_objs:
        contact_obj.tags.add(product.slug + "-added")

    return {
        "invoice_id": invoice.id,
        "contact_id": contact_obj.id,
    }


def logistics_is_installed():
    return "logistics" not in getattr(settings, "DISABLED_APPS", [])


def mail_managers_on_errors(process_name, error_msg, traceback_info=""):
    """
    Send error notification to the managers
    @param process_name: Name of the process or function with error.
    @param error_msg: Error message.
    """
    subject = f"System error happens in {process_name}"
    msg = f"System error occurs {process_name} runs with error: {error_msg}\n\n"
    if traceback_info:
        msg += traceback_info  # Add the stack trace
    mail_managers(subject=subject, message=msg)
