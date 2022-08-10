import requests, collections
from datetime import date, timedelta
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
    print("sending email {} to {}".format(email, mailtrain_list_id))
    url = '{}subscribe/{}'.format(settings.MAILTRAIN_API_URL, mailtrain_list_id)
    params = {'access_token': settings.MAILTRAIN_API_KEY}
    data = {'EMAIL': email}
    r = requests.post(url=url, params=params, data=data)
    print(r)


def delete_email_from_mailtrain_list(email, mailtrain_list_id):
    print("deleting email {} from {}".format(email, mailtrain_list_id))
    url = '{}delete/{}'.format(settings.MAILTRAIN_API_URL, mailtrain_list_id)
    params = {'access_token': settings.MAILTRAIN_API_KEY}
    data = {'EMAIL': email}
    r = requests.post(url=url, params=params, data=data)
    print(r)


def get_emails_from_mailtrain_list(mailtrain_list_id):
    emails = []
    url = '{}subscriptions/{}'.format(settings.MAILTRAIN_API_URL, mailtrain_list_id)
    params = {'access_token': settings.MAILTRAIN_API_KEY, 'limit': 30000}
    r = requests.get(url=url, params=params)
    data = r.json()
    for subscription in data['data']['subscriptions']:
        emails.append(subscription['email'])
    return emails


def calc_price_from_products(products_with_copies, frequency):
    """
    Returns the prices, we need the products already processed.
    """
    from core.models import Product, AdvancedDiscount

    total_price, discount_pct, frequency_discount_amount, frequency = 0, 0, 0, int(frequency)

    percentage_discount = None
    advanced_discount_list = []

    for product_id, copies in products_with_copies.items():
        product = Product.objects.get(pk=int(product_id))
        copies = int(copies)
        if getattr(settings, 'DEBUG_PRODUCTS', False):
            print(u"{} {} x{} = {}".format(product.name, copies, product.price, product.price * copies))
        if product.type == 'S':
            total_price += product.price * copies
        elif product.type == 'D':
            # Discounts are only applied once (TODO: Decide if we need to change this)
            total_price -= product.price
        elif product.type == 'P':
            percentage_discount = product
        elif product.type == 'A':
            advanced_discount_list.append(product)

    # After calculating the prices of the product, we check out every product in the advanced_discount_list
    for discount_product in advanced_discount_list:
        advanced_discount = AdvancedDiscount.objects.get(discount_product=discount_product)
        discounted_product_price = 0
        for product in advanced_discount.find_products.all():
            if product.id in products_with_copies.keys():
                if product.type == 'S':
                    discounted_product_price += int(products_with_copies[product.id]) * product.price
                else:
                    discounted_product_price -= int(products_with_copies[product.id]) * product.price
        if advanced_discount.value_mode == 1:
            discounted_product_price = advanced_discount.value
        else:
            discounted_product_price = round((discounted_product_price * advanced_discount.value) / 100)
        total_price -= discounted_product_price

    # After calculating the prices of S and D products, we need to calculate the one for P.
    # It's important that we only put one percentage discount product.
    if percentage_discount:
        percentage_discount_amount = round((total_price * percentage_discount.price) / 100)
        total_price -= percentage_discount_amount

    # Then we multiply all this by the frequenccy
    total_price = total_price * frequency
    # Next step is determining if there's a discount for frequency
    if frequency == 3:
        discount_pct = getattr(settings, 'DISCOUNT_3_MONTHS', 0)
    elif frequency == 6:
        discount_pct = getattr(settings, 'DISCOUNT_6_MONTHS', 0)
    if frequency == 12:
        discount_pct = getattr(settings, 'DISCOUNT_12_MONTHS', 0)
    if discount_pct:
        frequency_discount_amount = round((total_price * discount_pct) / 100)
        total_price -= frequency_discount_amount
    if getattr(settings, 'DEBUG_PRODUCTS', False):
        print("Total: {}\n\n".format(total_price))
    return int(round(total_price))


def process_products(input_product_dict):
    """
    Takes products from a product list (for example from a subscription products list) and turns them into new products
    that are already bundled. These will be executed in order of priority, from smallest to greatest.

    Each of the products must be a tuple with product and copies.
    """
    from core.models import Product, PriceRule

    input_product_ids = list(input_product_dict.keys())
    input_products = Product.objects.filter(id__in=input_product_ids)
    input_products_count = input_products.count()
    output_dict = {}
    for pricerule in PriceRule.objects.filter(active=True).order_by('priority'):
        exit_loop = False
        products_in_list_and_pool = []
        pool = pricerule.products_pool.all()
        not_pool = pricerule.products_not_pool.all()
        ignore_product_bundle = pricerule.ignore_product_bundle.all()
        if not_pool:
            for product in not_pool:
                if product in input_products or product.id in output_dict.keys():
                    # If any of the products is in the list of input products and on the not_pool, we skip the rule
                    exit_loop = True
                    break
        if exit_loop:
            continue
        if ignore_product_bundle:
            for bundle in ignore_product_bundle:
                if collections.Counter(list(input_products)) == collections.Counter(list(bundle.products.all())):
                    exit_loop = True
                    break
        if exit_loop:
            continue
        for input_product in input_products:
            if input_product in pricerule.products_pool.all():
                products_in_list_and_pool.append(input_product)
        if pricerule.add_wildcard:
            # If the product rule has a wildcard it means it has to be in the pool, and MUST NOT be the only product
            # in the mix.
            if input_products_count > 1 and len(products_in_list_and_pool) > 0:
                output_dict[pricerule.resulting_product.id] = input_product_dict[input_product_ids[0]]
        elif len(products_in_list_and_pool) == pricerule.amount_to_pick:
            if pricerule.mode == 1:
                # We use the copies for any of the products, the first one for instance, they should all be the same
                # since they're on the 'choose all products' mode.
                output_dict[pricerule.resulting_product.id] = input_product_dict[str(products_in_list_and_pool[0].id)]
                # We're going to exclude the products that were not used here so they can be used by other rules.
                for product in input_products:
                    if product in pool:
                        input_products = input_products.exclude(pk=product.id)
            elif pricerule.mode == 2:
                # This is if we only need to change one product into another. WIP.
                output_dict[pricerule.choose_one_product.id] = products_in_list_and_pool[0][1]
                for product in input_products:
                    if product == pricerule.choose_one_product:
                        # We're only going to replace the chosen product from the mix.
                        input_products = input_products.exclude(pk=product.id)
            elif pricerule.mode == 3:
                # We just add an extra product to the list. We're not going to remove them from input products.
                # Again we take the copies from the first product on the list. This might be dangerous, and might need
                # a different value. We might change it to 1.
                output_dict[pricerule.resulting_product.id] = input_product_dict[input_product_ids[0]]

    # In the end we will also add the remainder of the products that were not used to the output dictionary
    for product in input_products:
        output_dict[product.id] = input_product_dict[str(product.id)]
    return output_dict
