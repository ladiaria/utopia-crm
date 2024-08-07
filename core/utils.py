from datetime import date, timedelta
import collections
import requests
from requests.auth import HTTPBasicAuth
from requests.exceptions import ReadTimeout, RequestException
import html2text
from typing import Literal


from django.conf import settings
from django.core.validators import validate_email
from django.core.exceptions import ValidationError


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


# TODO: handle cases of setting missconf for the next 4 functions (mailtrain api calls)
def subscribe_email_to_mailtrain_list(email, mailtrain_list_id):
    if settings.DEBUG:
        print(("sending email {} to {}".format(email, mailtrain_list_id)))
    url = '{}subscribe/{}'.format(settings.MAILTRAIN_API_URL, mailtrain_list_id)
    params = {'access_token': settings.MAILTRAIN_API_KEY}
    return requests.post(url, params=params, data={'EMAIL': email})


def unsubscribe_email_from_mailtrain_list(email, mailtrain_list_id):
    if settings.DEBUG:
        print(("sending email {} to {}".format(email, mailtrain_list_id)))
    url = '{}unsubscribe/{}'.format(settings.MAILTRAIN_API_URL, mailtrain_list_id)
    params = {'access_token': settings.MAILTRAIN_API_KEY}
    return requests.post(url, params=params, data={'EMAIL': email})


def delete_email_from_mailtrain_list(email, mailtrain_list_id):
    if settings.DEBUG:
        print(("deleting email {} from {}".format(email, mailtrain_list_id)))
    url = '{}delete/{}'.format(settings.MAILTRAIN_API_URL, mailtrain_list_id)
    params = {'access_token': settings.MAILTRAIN_API_KEY}
    return requests.post(url, params=params, data={'EMAIL': email})


def get_mailtrain_lists(email):
    if not getattr(settings, 'MAILTRAIN_API_URL', None):
        return []
    url = '{}lists/{}'.format(settings.MAILTRAIN_API_URL, email)
    params = {'access_token': settings.MAILTRAIN_API_KEY}
    return [mlist["cid"] for mlist in requests.get(url, params=params).json()["data"] if mlist["status"] == 1]


def get_emails_from_mailtrain_list(mailtrain_list_id, status=None, limit=None):
    # TODO: A way to proceed in case the list has more emails than the limit (Mailtrain's default 10000) allows.
    # NOTE: The limit passed can be greater than the Mailtrain's default (10000)
    # Mailtrain's status ref: 1=Subscribed, 2=Unsubscribed ...
    emails = []
    url = '{}subscriptions/{}'.format(settings.MAILTRAIN_API_URL, mailtrain_list_id)
    params = {'access_token': settings.MAILTRAIN_API_KEY}
    if limit:
        params['limit'] = limit
    r = requests.get(url, params=params)
    data = r.json()
    for subscription in data['data']['subscriptions']:
        if not status or subscription["status"] == status:
            emails.append(subscription['email'])
    return emails


def user_mailtrain_lists(email):
    url = f'{settings.MAILTRAIN_API_URL}/lists/{email}'
    params = {'access_token': settings.MAILTRAIN_API_KEY}
    r = requests.get(url, params=params)
    try:
        r.raise_for_status()
        json_response = r.json()
        items = json_response["data"]
        # make a dictionary with list_ids, names, and status for each list
        mailtrain_lists = [
            {'name': item.get('name'), 'status': item.get('status'), 'cid': item.get('cid')} for item in items
        ]
        return mailtrain_lists
    except Exception:
        raise


def calc_price_from_products(products_with_copies, frequency, debug_id=""):
    """
    Returns the prices, we need the products already processed.
    """
    from core.models import Product, AdvancedDiscount

    total_price, discount_pct, frequency = 0, 0, int(frequency)

    percentage_discount, debug = None, getattr(settings, 'DEBUG_PRODUCTS', False)
    if debug and debug_id:
        debug_id += ": "
    all_list, discount_list, non_discount_list, advanced_discount_list = products_with_copies.items(), [], [], []

    # 1. partition the input by discount products / non discount products
    for product_id, copies in all_list:
        try:
            product = Product.objects.get(pk=int(product_id))
        except Product.DoesNotExist:
            pass
        else:
            (non_discount_list if product.type == 'S' else discount_list).append(product)

    # 2. obtain 2 total cost amounts: affectable/non-affectable by discounts
    total_affectable, total_non_affectable = 0, 0
    for product in non_discount_list:
        copies = int(products_with_copies[product.id])
        if debug:
            print(
                f"{debug_id}{product.name} {copies}x{'-' if product.type == 'D' else ''}"
                f"{product.price} = {'-' if product.type == 'D' else ''}{product.price * copies}"
            )
        # check first if this product is affected to any of the discounts
        affectable = False
        for discount_product in [d for d in discount_list if d.target_product == product]:
            affectable_delta = product.price * copies
            if discount_product.type == "D":
                affectable_delta -= discount_product.price * int(products_with_copies[discount_product.id])
            elif discount_product.type == "P":
                affectable_delta_discount = (affectable_delta * discount_product.price) / 100
                affectable_delta -= affectable_delta_discount
            total_affectable += affectable_delta
            discount_list.remove(discount_product)
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
    for product in discount_list:
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


def updatewebuser(id, email, newemail, field, value):
    """
    Esta es la funcion que hace el POST hacia la web, siempre recibe el mail actual y el nuevo (el que se esta
    actualizando) porque son necesarios para buscar la ficha en la web.
    Ademas recibe el nombre de campo y el nuevo valor actualizado, son utiles cuando se quiere sincronizar otros
    campos.
    ATENCION: No se sincroniza cuando el nuevo valor del campo es None
    """
    # TODO: translate docstring to english
    # TODO: try to use the next function from here (DRY)
    api_url, api_key = (getattr(settings, attr) for attr in ("WEB_UPDATE_USER_URI", "LDSOCIAL_API_KEY"))
    if api_url and api_key:
        data = {
            "contact_id": id,
            "email": email,
            "newemail": newemail,
            "field": field,
            "value": value,
        }
        post_kwargs = {
            "headers": {'Authorization': 'Api-Key ' + api_key},
            "data": data,
            "timeout": (5, 20),
            "verify": settings.WEB_UPDATE_USER_VERIFY_SSL,
        }
        http_basic_auth = settings.WEB_UPDATE_HTTP_BASIC_AUTH
        if http_basic_auth:
            post_kwargs["auth"] = HTTPBasicAuth(*http_basic_auth)
        r = requests.post(api_url, **post_kwargs)
        if settings.DEBUG:
            print("DEBUG: updatewebuser api response content: " + html2text.html2text(r.content.decode()).strip())
        r.raise_for_status()  # TODO: is there a way to "attach" the exception content (if any) to this call?


def post_to_cms_rest_api(api_name, api_uri, post_data):
    api_key = settings.LDSOCIAL_API_KEY
    if not (api_uri or api_key):
        return "ERROR"
    post_kwargs = {
        "headers": {'Authorization': 'Api-Key ' + api_key},
        "data": post_data,
        "timeout": (5, 20),
        "verify": settings.WEB_UPDATE_USER_VERIFY_SSL,
    }
    http_basic_auth = settings.WEB_UPDATE_HTTP_BASIC_AUTH
    if http_basic_auth:
        post_kwargs["auth"] = HTTPBasicAuth(*http_basic_auth)
    try:
        if settings.DEBUG:
            print("DEBUG: %s to %s with post_data='%s'" % (api_name, api_uri, post_data))
        r = requests.post(api_uri, **post_kwargs)
        r.raise_for_status()
    except ReadTimeout:
        return "TIMEOUT"
    except RequestException:
        return "ERROR"
    else:
        result = r.json()
        if settings.DEBUG:
            print("DEBUG: %s POST result: %s" % (api_name, result))
        return result


def validateEmailOnWeb(contact_id, email):
    return post_to_cms_rest_api(
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
