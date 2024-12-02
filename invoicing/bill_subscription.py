from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from django.utils.formats import format_lazy


from core.models import Subscription, Product, SubscriptionProduct, AdvancedDiscount
from invoicing.models import Invoice, InvoiceItem


def bill_subscription(subscription_id, billing_date=None, dpp=10):
    """
    Bills a single subscription into an only invoice. Returns the created invoice.
    """
    # Safely get settings with default values
    billing_extra_days = getattr(settings, 'BILLING_EXTRA_DAYS', 0)
    force_dummy_missing_billing_data = getattr(settings, 'FORCE_DUMMY_MISSING_BILLING_DATA', False)
    require_route_for_billing = getattr(settings, 'REQUIRE_ROUTE_FOR_BILLING', False)
    exclude_routes_from_billing_list = getattr(settings, 'EXCLUDE_ROUTES_FROM_BILLING_LIST', [])
    envelope_price = getattr(settings, 'ENVELOPE_PRICE', 0)
    debug_products = getattr(settings, 'DEBUG_PRODUCTS', settings.DEBUG)

    billing_date = billing_date or date.today()
    subscription = get_object_or_404(Subscription, pk=subscription_id)
    invoice, invoice_items, balance_item = None, None, None

    # Check that the subscription is active
    assert subscription.active, _('This subscription is not active and should not be billed.')

    # Check that the subscription is normal
    assert subscription.type in ('N', 'C'), _('This subscription is not normal or corporate and should not be billed.')

    # Check that the next billing date exists or we need to raise an exception.
    assert subscription.next_billing, _("Could not bill because next billing date does not exist")

    # Check that the subscription has a payment type
    assert subscription.payment_type, _("The subscription has no payment type, it can't be billed")

    # Check that the subscription's next billing is smaller than end date if it has it
    if subscription.end_date:
        error_msg = _("This subscription has an end date greater than its next billing")
        assert subscription.next_billing < subscription.end_date, error_msg

    if subscription.next_billing > billing_date + timedelta(billing_extra_days):
        raise Exception(_('This subscription should not be billed yet.'))

    # We need to get all the subscription data. The priority is defined in the billing_priority column of the product.
    # If this first product doesn't have the required data, then we can't bill the subscription.
    billing_data = subscription.get_billing_data_by_priority()

    if not billing_data and not force_dummy_missing_billing_data:
        raise Exception(
            f"Subscription {subscription.id} for contact {subscription.contact.id} contains no billing data."
        )

    if billing_data and billing_data["address"] is None:
        raise Exception(
            f"Subscription {subscription.id} for contact {subscription.contact.id} requires an address to be billed."
        )

    if billing_data and require_route_for_billing:
        if billing_data["route"] is None:
            raise Exception(
                f"Subscription {subscription.id} for contact {subscription.contact.id} requires a route to be billed."
            )

        elif billing_data["route"] in exclude_routes_from_billing_list:
            raise Exception(
                f"Subscription {subscription.id} for contact {subscription.contact.id} can't be billed since it's on"
                f"route {billing_data['route']}."
            )

    invoice_items = []

    # TODO: the same calculation code is repeated in utils.calc_price_from_products, but here we need to add items,
    #       we can somehow pass the invoice to that function to deduplicate calculation code, for example.
    # First we're going to form all the invoiceitems from the processed products the subscription has.
    # This gives a dictionary with product_id and copies so we need to call the items of said dictionary
    percentage_discount_product = None
    product_summary = subscription.product_summary(with_pauses=True)
    all_list, discount_list, non_discount_list, advanced_discount_list = product_summary.items(), [], [], []

    # 1. partition the input by discount products / non discount products
    for product_id, copies in all_list:
        try:
            product = Product.objects.get(pk=int(product_id))
        except Product.DoesNotExist:
            pass
        else:
            (
                non_discount_list
                if product.type in (Product.ProductTypeChoices.SUBSCRIPTION, Product.ProductTypeChoices.OTHER)
                else discount_list
            ).append(product)

    # 2. obtain 2 total cost amounts: affectable/non-affectable by discounts
    subtotal_affectable, subtotal_non_affectable = 0.0, 0.0
    for product in non_discount_list:
        copies = int(product_summary[product.id])

        if debug_products:
            print(
                f"DEBUG: bill_subscription: {product.name} {copies}x{'-' if product.type == 'D' else ''}"
                f"{product.price} = {'-' if product.type == 'D' else ''}{product.price * copies}"
            )

        # For each product we're making an invoiceitem. Items of frequency 4 are one-shot products, so we'll remove
        # them from the subscription after billing them. They also don't have a frequency, so we'll bill them once.
        frequency_extra = (
            _(' {} months'.format(subscription.frequency))
            if subscription.frequency > 1 and product.edition_frequency != 4
            else ''
        )
        item = InvoiceItem(
            subscription=subscription,
            invoice=invoice,
            copies=copies,
            price=product.price,
            product=product,
            description=format_lazy('{} {}', product.name, frequency_extra),
            type='I',
            amount=product.price * copies,
        )
        invoice_items.append(item)

        # check first if this product is affected to any of the discounts
        affectable = False
        for discount_product in [d for d in discount_list if d.target_product == product]:
            item_discount = InvoiceItem()
            frequency_extra = _(' {} months'.format(subscription.frequency)) if subscription.frequency > 1 else ''
            item_discount.description = format_lazy('{} {}', discount_product.name, frequency_extra)
            item_discount.price = discount_product.price * subscription.frequency
            item_discount.product = discount_product
            item_discount.copies = int(product_summary[discount_product.id])
            item_discount.type = "D"
            affectable_delta = float(item.amount)
            if discount_product.type == "D":
                item_discount.type_dr = 1
                affectable_delta -= float(item_discount.price * item_discount.copies)
            elif discount_product.type == "P":
                affectable_delta_discount = (affectable_delta * float(discount_product.price)) / 100
                affectable_delta -= affectable_delta_discount
            item_discount.amount = item_discount.price * item_discount.copies
            subtotal_affectable += affectable_delta
            invoice_items.append(item_discount)
            discount_list.remove(discount_product)
            affectable = True
            break
        if not affectable:
            # not affected by discounts but the product price can be also "affectable" if has_implicit_discount
            product_delta = float(item.amount)
            if product.has_implicit_discount:
                subtotal_affectable += product_delta
            else:
                subtotal_non_affectable += product_delta

    # 3. iterate over discounts left
    for product in discount_list:
        if product.type == 'D':
            item = InvoiceItem()
            frequency_extra = _(' {} months'.format(subscription.frequency)) if subscription.frequency > 1 else ''
            item.description = format_lazy('{} {}', product.name, frequency_extra)
            item.price = product.price * subscription.frequency
            item.product = product
            item.copies = int(product_summary[product.id])
            item.type = 'D'  # This means this is a discount item
            # We'll use the type of discount/surcharge of 1, that uses the numeric value instead of a percentage.
            item.type_dr = 1
            item.amount = item.price * item.copies
            # save all the package
            invoice_items.append(item)
            subtotal_non_affectable -= float(item.amount)
        elif product.type == 'P':
            # If it's a percentage discount we'll save it for last, after the entire price has been calculated
            percentage_discount_product = product
        elif product.type == 'A':
            # if it's an advanced discount, save it for last too
            advanced_discount_list.append(product)

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
                    if product.id in product_summary:
                        if product.type == 'S':
                            discounted_product_price += int(product_summary[product.id]) * product.price
                        else:
                            discounted_product_price -= int(product_summary[product.id]) * product.price
                discounted_product_price = (discounted_product_price * advanced_discount.value) / 100
            item = InvoiceItem()
            frequency_extra = _(' {} months'.format(subscription.frequency)) if subscription.frequency > 1 else ''
            item.description = format_lazy('{} {}', discount_product.name, frequency_extra)
            item.price = discounted_product_price  # This is to calculate the $
            item.type = 'D'
            item.type_dr = 1
            item.product = discount_product
            item.copies = 1
            item.amount = item.price  # Copies is 1 so this is also the amount
            invoice_items.append(item)
            subtotal_non_affectable -= item.amount

    if percentage_discount_product:
        # Then if we have the percentage discount, we'll calculate how much it is. We do this last to make sure
        # the price is calculated with the entire sum of the subscription
        item = InvoiceItem()
        frequency_extra = _(' {} months'.format(subscription.frequency)) if subscription.frequency > 1 else ''
        item.description = format_lazy('{} {}', percentage_discount_product.name, frequency_extra)
        item.price = (subtotal_non_affectable * float(percentage_discount_product.price)) / 100  # calculate the $
        item.type = 'D'
        item.type_dr = 1
        item.product = percentage_discount_product
        item.copies = 1
        item.amount = item.price  # Copies is 1 so this is also the amount
        subtotal_non_affectable -= item.amount
        invoice_items.append(item)

    # After adding all of the invoiceitems, we need to check if the subscription has an envelope. In future reviews
    # this should be deprecated and envelopes should be its own product, because here you'd end up adding envelopes
    # to digital products potentially. Fancy digital envelopes huh?
    if envelope_price and SubscriptionProduct.objects.filter(subscription=subscription, has_envelope=1).exists():
        # Get the amount of days per week the subscription gets the paper
        products_with_envelope_count = SubscriptionProduct.objects.filter(
            subscription=subscription, has_envelope=1
        ).count()
        # Then we multiply the amount of days by 4.25 (average of weeks per
        # month) and that amount by the price of the envelope
        amount = products_with_envelope_count * envelope_price * subscription.frequency
        # We now pack the value into an InvoiceItem and add it to the list
        envelope_item = InvoiceItem()
        envelope_item.description = _('Envelope')
        envelope_item.amount = amount
        envelope_item.subscription = subscription
        invoice_items.append(envelope_item)
        subtotal_affectable += envelope_item.amount

    expiration_date = billing_date + timedelta(int(dpp))
    service_from = subscription.next_billing

    # check if it is necessary to add discounts by frequency.
    discount_pct = subscription.get_frequency_discount()
    if discount_pct:
        # Pack the discount invoiceitem and add it to the list
        frequency_discount_item = InvoiceItem()
        frequency_discount_item.description = _(
            '{} months discount ({} discount)'.format(subscription.frequency, discount_pct)
        )
        frequency_discount_item.amount = (subtotal_non_affectable * discount_pct) / 100
        # 1 means it's a plain value. This is just in case you want to use percentage discounts.
        frequency_discount_item.type_dr = 1
        # This means the item is a discount.
        frequency_discount_item.type = 'D'
        invoice_items.append(frequency_discount_item)
        subtotal_non_affectable -= frequency_discount_item.amount

    if invoice_items:
        try:
            amount = subtotal_affectable + subtotal_non_affectable

            # After we calculated the invoice amount, we'll make sure the balance item isn't
            # greater than the invoice, we don't want a negative value invoice!
            if subscription.balance and subscription.balance != 0:
                balance_item = InvoiceItem()
                if subscription.balance > 0:
                    # If the balance is positive, it means this invoice will have a discount.
                    balance_item.description = _('Balance')
                    balance_item.type = 'D'  # This means the item is a discount.
                    if subscription.balance > amount:
                        balance_item.amount = amount
                    else:
                        balance_item.amount = subscription.balance
                    balance_item.type_dr = 1  # 1 means it's a plain value
                    amount -= float(balance_item.amount)  # And then we subtract that value from the invoice
                elif subscription.balance < 0:
                    # If the balance is negative, it means the person owes us money, we'll make a surcharge.
                    balance_item.description = _('Balance owed')
                    balance_item.type_dr = 1  # 1 means it's a plain value
                    balance_item.type = 'R'  # This means the item is a surcharge
                    balance_item.amount = abs(subscription.balance)  # The entire balance is applied to the item
                    amount += float(balance_item.amount)  # And then we add that value to the invoice
                # We don't want any negative shenanigans so we'll use the absolute.
                balance_item.amount = abs(balance_item.amount)
                invoice_items.append(balance_item)

            # Finally we make the rounding and add the invoiceitem needed. This had to be changed to be made after the
            # balance because this was causing to make the invoices to have decimal places.
            if amount != round(amount):
                amount_rounded = round(amount) - amount
                round_item = InvoiceItem()
                if amount_rounded < 0:
                    round_item.type = 'D'
                elif amount_rounded > 0:
                    round_item.type = 'R'
                round_item.description = _('Rounding')
                round_item.type_dr = 1
                round_item.amount = abs(amount_rounded)
                amount = int(round(amount))
                invoice_items.append(round_item)

            # If the subscription doesn't have next_billing, we'll create one using the start_date of the subscription.

            payment_method = subscription.payment_type

            # Meanwhile we'll create the invoice object
            if amount > 0:
                invoice = Invoice.objects.create(
                    contact=subscription.get_billing_contact(),
                    payment_type=payment_method,
                    creation_date=billing_date,
                    service_from=service_from,
                    service_to=service_from + relativedelta(months=subscription.frequency),
                    billing_name=billing_data['name'],
                    billing_address=billing_data['address'],
                    billing_state=billing_data['state'],
                    billing_city=billing_data['city'],
                    route=billing_data['route'],
                    order=billing_data['order'],
                    expiration_date=expiration_date,
                    billing_document=subscription.get_billing_document(),
                    subscription=subscription,
                    amount=amount,
                )

                # We add all invoice items to the invoice. We need to remove the products that are one-shot
                for item in invoice_items:
                    item.save()
                    invoice.invoiceitem_set.add(item)
                    if item.product and item.product.edition_frequency == 4:  # One-shot
                        invoice.subscription.remove_product(item.product)

                # When the invoice has finally been created and every date has been moved where it should have been,
                # we're going to check if there's any temporary discounts, and remove them if it applies.
                ii_qs = invoice.invoiceitem_set.filter(product__temporary_discount_months__gte=1)
                for ii in ii_qs:
                    temporary_discount = ii.product
                    months = temporary_discount.temporary_discount_months
                    if invoice.subscription.months_in_invoices_with_product(temporary_discount.slug) >= months:
                        invoice.subscription.remove_product(temporary_discount)

            # Then finally we need to change everything on the subscription
            if subscription.balance:
                if subscription.balance > 0 and balance_item:
                    subscription.balance -= balance_item.amount  # Then subtract the balance
                if subscription.balance <= 0:
                    subscription.balance = None  # Then if it is zero or less, remove it completely.
            subscription.next_billing = (subscription.next_billing or subscription.start_date) + relativedelta(
                months=subscription.frequency
            )
            subscription.save()
            # We do this here because we also need to change the subscription dates even if the amount is 0, but
            # we don't want to execute anything of this if the invoice creation process failed for whatever reason.
            assert amount, _("This subscription wasn't billed since amount is 0")

        except Exception as e:
            raise Exception("Contact {} Subscription {}: {}".format(subscription.contact.id, subscription.id, e))
    else:
        # If for whatever reasons there are no invoice items, we did something wrong, we'll have to return nothing.
        return None
    return invoice
