// physicalcount_admin.js - Auto-llenar cantidad disponible

(function() {
    'use strict';
    
    console.log('🔴 physicalcount_admin.js cargado');
    
    function setupAutoFill() {
        console.log('🔴 Ejecutando setupAutoFill...');
        
        // ✅ Buscar los campos
        var productSelect = document.getElementById('id_product');
        var locationSelect = document.getElementById('id_location');
        var availableField = document.getElementById('id_available_quantity');
        var adjustmentField = document.getElementById('id_adjustment_quantity');
        
        console.log('🔴 Producto:', productSelect);
        console.log('🔴 Ubicación:', locationSelect);
        console.log('🔴 Cantidad disponible:', availableField);
        console.log('🔴 Cantidad a ajustar:', adjustmentField);
        
        if (!productSelect || !locationSelect || !availableField) {
            console.log('❌ Campos no encontrados, reintentando en 500ms...');
            setTimeout(setupAutoFill, 500);
            return;
        }
        
        console.log('✅ Todos los campos encontrados');
        
        function getAvailableQuantity() {
            var productId = productSelect.value;
            var locationId = locationSelect.value;
            
            console.log('🔴 Buscando cantidad para producto:', productId, 'ubicación:', locationId);
            
            if (!productId || !locationId) {
                availableField.value = 0;
                return;
            }
            
            // ✅ Obtener la cantidad disponible via AJAX
            fetch('/admin/inventory/get-available-quantity/?product_id=' + productId + '&location_id=' + locationId, {
                method: 'GET',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(response => response.json())
            .then(data => {
                console.log('🔴 Datos recibidos:', data);
                if (data.quantity !== undefined) {
                    availableField.value = data.quantity || 0;
                    availableField.dispatchEvent(new Event('change'));
                    
                    // ✅ Si adjustment_quantity está vacío o es 0, copiar el valor
                    if (adjustmentField && (!adjustmentField.value || adjustmentField.value == 0)) {
                        adjustmentField.value = availableField.value;
                    }
                }
            })
            .catch(error => {
                console.error('❌ Error:', error);
                availableField.value = 0;
            });
        }
        
        // ✅ Eventos para auto-llenar
        productSelect.addEventListener('change', getAvailableQuantity);
        locationSelect.addEventListener('change', getAvailableQuantity);
        
        // ✅ Si Select2 está activo, también escuchar sus eventos
        try {
            if (typeof django !== 'undefined' && django.jQuery) {
                django.jQuery(productSelect).on('select2:select', function(e) {
                    console.log('🔴 Select2: producto seleccionado');
                    setTimeout(getAvailableQuantity, 100);
                });
                django.jQuery(locationSelect).on('select2:select', function(e) {
                    console.log('🔴 Select2: ubicación seleccionada');
                    setTimeout(getAvailableQuantity, 100);
                });
            }
        } catch(e) {
            console.log('⚠️ Select2 no disponible, usando eventos nativos');
        }
        
        // ✅ Ejecutar al cargar si ya hay valores
        if (productSelect.value && locationSelect.value) {
            console.log('🔴 Ejecutando carga inicial...');
            setTimeout(getAvailableQuantity, 300);
        }
    }
    
    // ✅ Intentar múltiples veces
    document.addEventListener('DOMContentLoaded', function() {
        console.log('🔴 DOM Content Loaded');
        setTimeout(setupAutoFill, 200);
        setTimeout(setupAutoFill, 500);
        setTimeout(setupAutoFill, 1000);
    });
    
    // ✅ También cuando se agregan nuevos formsets
    document.addEventListener('formset:added', function() {
        console.log('🔴 formset:added detectado');
        setTimeout(setupAutoFill, 500);
    });
    
})();