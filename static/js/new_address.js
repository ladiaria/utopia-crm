/*
 * "New address" opened from a sale: the sale's address lists catch up on their own.
 *
 * The link (an <a class="new_address_link"> with data-contact-id and data-addresses-url, see _new_address_link.html)
 * opens the address screen in a window of its own, one per contact, so clicking it again brings that window back
 * instead of opening a second form. When the address is saved there, the window announces it on the
 * "utopia-addresses" BroadcastChannel (announceNewAddress) and closes itself. The sale's page hears it and reloads
 * its address selectors from the contact's addresses, keeping what each one had selected.
 *
 * Before, the sale only saw the new address after pressing "Reload addresses". Whoever did not press it took the
 * address for lost and loaded it again, and the contact ended up with the same address several times.
 */
(function () {
  var CHANNEL_NAME = "utopia-addresses";
  // The product selectors, plus the billing and default address of the subscription forms
  var SELECTORS = ".address_selector, #id_billing_address, #id_default_address";

  function openChannel() {
    return "BroadcastChannel" in window ? new BroadcastChannel(CHANNEL_NAME) : null;
  }

  // Called by the window where the address was saved, or chosen among the contact's own (existed). Returns false when
  // the browser can't tell the other windows.
  window.announceNewAddress = function (contactId, addressId, existed) {
    var channel = openChannel();
    if (!channel) {
      return false;
    }
    channel.postMessage({ contactId: String(contactId), addressId: String(addressId), existed: Boolean(existed) });
    channel.close();
    return true;
  };

  function reloadAddressSelectors(url, done) {
    $.ajax({
      url: url,
      method: "POST",
      dataType: "json",
      success: function (data) {
        $(SELECTORS).each(function () {
          var select = $(this);
          var selectedValue = select.val();
          // The "choose an address" option, when the select has one, stays first
          var blankOption = select.find("option[value='']").first();
          select.empty();
          if (blankOption.length) {
            select.append(blankOption);
          }
          $.each(data, function (index, item) {
            var option = $("<option>").text(item.text).val(item.value);
            if (String(item.value) === String(selectedValue)) {
              option.prop("selected", true);
            }
            select.append(option);
          });
        });
        // Only the product selectors: a change on the default address would copy it onto every product
        $(".address_selector").trigger("change");
        done(data);
      },
    });
  }

  $(function () {
    var links = $(".new_address_link");
    if (!links.length) {
      return;
    }
    var contactId = String(links.first().data("contact-id"));
    var url = links.first().data("addresses-url");

    function showNewAddress(addressId, existed) {
      reloadAddressSelectors(url, function (data) {
        var added = $.grep(data, function (item) {
          return String(item.value) === String(addressId);
        })[0];
        if (added) {
          $(".new_address_notice .new_address_text").text(added.text);
          $(".new_address_notice .new_address_added").toggleClass("d-none", existed);
          $(".new_address_notice .new_address_existing").toggleClass("d-none", !existed);
          $(".new_address_notice").removeClass("d-none");
          $(".no_addresses_warning").addClass("d-none");
        }
      });
    }

    links.on("click", function (event) {
      // A window opened by this script may close itself once the address is saved
      var addressWindow = window.open(this.href, "new_address_" + contactId);
      if (addressWindow) {
        event.preventDefault();
        addressWindow.focus();
      }
    });

    var channel = openChannel();
    if (channel) {
      channel.onmessage = function (event) {
        if (event.data && event.data.contactId === contactId) {
          showNewAddress(event.data.addressId, Boolean(event.data.existed));
        }
      };
    } else {
      // No BroadcastChannel: reload the lists whenever the agent comes back to this page
      document.addEventListener("visibilitychange", function () {
        if (document.visibilityState === "visible") {
          reloadAddressSelectors(url, function () {});
        }
      });
    }
  });
})();
