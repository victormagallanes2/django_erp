// django_erp/static/admin/js/sale_order_admin.js

(function($) {
    'use strict';

    $(document).ready(function() {
        
        // ✅ Función para obtener precio del producto via AJAX
        function getProductPrice(productId, callback) {
            $.ajax({
                url: '/admin/sales/get-product-price/',
                data: {'product_id': productId},
                success: function(data) {
                    callback(data.unit_price || 0);
                },
                error: function() {
                    callback(0);
                }
            });
        }

        // ✅ Función para recalcular una línea
        function recalculateLine(row) {
            var quantity = parseFloat(row.find('input[id$=quantity]').val()) || 0;
            var unitPrice = parseFloat(row.find('input[id$=unit_price]').val()) || 0;
            var subtotal = quantity * unitPrice;
            
            // Actualizar subtotal
            var subtotalField = row.find('.field-subtotal');
            if (subtotalField.length) {
                subtotalField.text(subtotal.toFixed(2));
            }
            
            // Actualizar input oculto de subtotal si existe
            var subtotalInput = row.find('input[id$=subtotal]');
            if (subtotalInput.length) {
                subtotalInput.val(subtotal.toFixed(2));
            }
            
            return subtotal;
        }

        // ✅ Función para recalcular todos los totales
        function recalculateTotals() {
            var subtotal = 0;
            var taxRate = 19; // IVA por defecto
            
            $('.inline-group .dynamic-saleorder-lines tbody tr:visible').each(function() {
                var quantity = parseFloat($(this).find('input[id$=quantity]').val()) || 0;
                var unitPrice = parseFloat($(this).find('input[id$=unit_price]').val()) || 0;
                subtotal += quantity * unitPrice;
            });
            
            var tax = subtotal * (taxRate / 100);
            var total = subtotal + tax;
            
            $('#id_subtotal').val(subtotal.toFixed(2));
            $('#id_tax').val(tax.toFixed(2));
            $('#id_total').val(total.toFixed(2));
        }

        // ✅ Evento: Cambio de producto (autocompletar precio)
        $(document).on('change', '.inline-group .dynamic-saleorder-lines select[id$=product]', function() {
            var row = $(this).closest('tr');
            var productId = $(this).val();
            
            if (productId) {
                getProductPrice(productId, function(price) {
                    var priceInput = row.find('input[id$=unit_price]');
                    if (priceInput.length) {
                        priceInput.val(price);
                    }
                    recalculateLine(row);
                    recalculateTotals();
                });
                
                // Ocultar campos de servicio
                row.find('input[id$=product_name]').closest('.field-box').hide();
                row.find('input[id$=location_code]').closest('.field-box').hide();
                
            } else {
                // Mostrar campos de servicio
                row.find('input[id$=product_name]').closest('.field-box').show();
                row.find('input[id$=location_code]').closest('.field-box').show();
                recalculateLine(row);
                recalculateTotals();
            }
        });

        // ✅ Evento: Cambio de cantidad o precio
        $(document).on('change keyup', '.inline-group .dynamic-saleorder-lines input[id$=quantity], .inline-group .dynamic-saleorder-lines input[id$=unit_price]', function() {
            var row = $(this).closest('tr');
            recalculateLine(row);
            recalculateTotals();
        });

        // ✅ Evento: Agregar nueva línea
        $(document).on('click', '.inline-group .add-row a', function() {
            setTimeout(function() {
                var lastRow = $('.inline-group .dynamic-saleorder-lines tbody tr:last');
                if (lastRow.length) {
                    // Configurar eventos para productos
                    lastRow.find('select[id$=product]').on('change', function() {
                        var row = $(this).closest('tr');
                        var productId = $(this).val();
                        if (productId) {
                            getProductPrice(productId, function(price) {
                                var priceInput = row.find('input[id$=unit_price]');
                                if (priceInput.length) {
                                    priceInput.val(price);
                                }
                                recalculateLine(row);
                                recalculateTotals();
                            });
                            row.find('input[id$=product_name]').closest('.field-box').hide();
                            row.find('input[id$=location_code]').closest('.field-box').hide();
                        } else {
                            row.find('input[id$=product_name]').closest('.field-box').show();
                            row.find('input[id$=location_code]').closest('.field-box').show();
                            recalculateLine(row);
                            recalculateTotals();
                        }
                    });
                    
                    // Configurar eventos para cantidad y precio
                    lastRow.find('input[id$=quantity], input[id$=unit_price]').on('change keyup', function() {
                        var row = $(this).closest('tr');
                        recalculateLine(row);
                        recalculateTotals();
                    });
                    
                    // Si la línea nueva no tiene producto, mostrar campos de servicio
                    var productSelect = lastRow.find('select[id$=product]');
                    if (productSelect.length && !productSelect.val()) {
                        lastRow.find('input[id$=product_name]').closest('.field-box').show();
                        lastRow.find('input[id$=location_code]').closest('.field-box').show();
                    }
                }
            }, 100);
        });

        // ✅ Configurar líneas existentes al cargar
        setTimeout(function() {
            $('.inline-group .dynamic-saleorder-lines tbody tr').each(function() {
                var row = $(this);
                var productSelect = row.find('select[id$=product]');
                
                if (productSelect.length && !productSelect.val()) {
                    row.find('input[id$=product_name]').closest('.field-box').show();
                    row.find('input[id$=location_code]').closest('.field-box').show();
                } else {
                    row.find('input[id$=product_name]').closest('.field-box').hide();
                    row.find('input[id$=location_code]').closest('.field-box').hide();
                }
                
                recalculateLine(row);
            });
            recalculateTotals();
        }, 500);

    });
})(django.jQuery);