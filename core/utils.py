from datetime import date, timedelta
from csv import reader
import requests, collections

from django.conf import settings


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


def subscribe_email_to_mailtrain_list(email, mailtrain_list_id):
    if settings.DEBUG:
        print(("sending email {} to {}".format(email, mailtrain_list_id)))
    url = '{}subscribe/{}'.format(settings.MAILTRAIN_API_URL, mailtrain_list_id)
    params = {'access_token': settings.MAILTRAIN_API_KEY}
    data = {'EMAIL': email}
    r = requests.post(url=url, params=params, data=data)
    return r


def delete_email_from_mailtrain_list(email, mailtrain_list_id):
    if settings.DEBUG:
        print(("deleting email {} from {}".format(email, mailtrain_list_id)))
    url = '{}delete/{}'.format(settings.MAILTRAIN_API_URL, mailtrain_list_id)
    params = {'access_token': settings.MAILTRAIN_API_KEY}
    data = {'EMAIL': email}
    r = requests.post(url=url, params=params, data=data)
    return r


def get_emails_from_mailtrain_list(mailtrain_list_id):
    emails = []
    url = '{}subscriptions/{}'.format(settings.MAILTRAIN_API_URL, mailtrain_list_id)
    params = {'access_token': settings.MAILTRAIN_API_KEY, 'limit': 30000}
    r = requests.get(url=url, params=params)
    data = r.json()
    for subscription in data['data']['subscriptions']:
        emails.append(subscription['email'])
    return emails


def calc_price_from_products(products_with_copies, frequency, debug_id=""):
    """
    Returns the prices, we need the products already processed.
    """
    from core.models import Product, AdvancedDiscount

    total_price, discount_pct, frequency_discount_amount, frequency = 0, 0, 0, int(frequency)

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


def process_products(input_product_dict):
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
            if (
                (pricerule.amount_to_pick_condition == "eq" and list_and_pool_len == pricerule.amount_to_pick)
                or (pricerule.amount_to_pick_condition == "gt" and list_and_pool_len > pricerule.amount_to_pick)
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
