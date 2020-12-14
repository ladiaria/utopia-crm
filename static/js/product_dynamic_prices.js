function loadDynamicPrices(){
    var product_data = {};
    $('.product_checkbox:checked').each(function(i){
        var copies_id = '#copies-' + $(this).val();
        product_data[$(this).val()] = $(copies_id).val();
    });
    product_data['frequency'] = $('#id_frequency').val()
    $.ajax({
        method: "POST",
        url: "/support/api_dynamic_prices/",
        data: product_data,
        success: function(data){
            $('#price_amount').text(data['price']);
        },
        error: function(){
            console.log('Error');
        }
    });
};

$(function(){
    loadDynamicPrices();
    $('.product_checkbox').click(function(){
        loadDynamicPrices();
    });
    $('#id_frequency').change(function(){
        loadDynamicPrices();
    });
    $('input[name^="copies"]').change(function(){
        loadDynamicPrices();
    });
});
