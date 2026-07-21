// django_erp/static/admin/js/invoice_admin.js

console.log("🔴 SCRIPT DE FACTURACIÓN CARGADO");

// ============================================================
// ✅ NUEVAS FUNCIONES PARA MODO OFFLINE
// ============================================================

// ✅ Generar UUID
function generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

// ✅ Función para recolectar datos de la factura
function collectInvoiceData() {
    const invoiceData = {
        uuid: generateUUID(),
        number: document.getElementById('id_number')?.value || 'FAC-OFFLINE-0001',
        customer_name: document.getElementById('id_customer_name')?.value || 'Cliente Offline',
        customer_rif: document.getElementById('id_customer_rif')?.value || '',
        customer_address: document.getElementById('id_customer_address')?.value || '',
        subtotal: parseFloat(document.getElementById('id_subtotal_display')?.value) || 0,
        tax: parseFloat(document.getElementById('id_tax_display')?.value) || 0,
        total: parseFloat(document.getElementById('id_total_display')?.value) || 0,
        tax_rate: 16,
        note: document.getElementById('id_note')?.value || '',
        lines: [],
        device_id: localStorage.getItem('device_id') || 'desconocido',
        created_at_local: new Date().toISOString()
    };
    
    // ✅ Recolectar líneas
    const rows = document.querySelectorAll('tr.form-row');
    rows.forEach(function(row) {
        const productNameInput = row.querySelector('input[name$="product_name"]');
        const productCodeInput = row.querySelector('input[name$="product_code"]');
        const qtyInput = row.querySelector('input[name$="quantity"]');
        const priceInput = row.querySelector('input[name$="unit_price"]');
        
        const productName = productNameInput?.value || productCodeInput?.value || 'Producto sin nombre';
        const quantity = parseFloat(qtyInput?.value) || 1;
        const unitPrice = parseFloat(priceInput?.value) || 0;
        
        if (quantity > 0 && unitPrice >= 0) {
            invoiceData.lines.push({
                product_name: productName,
                product_code: productCodeInput?.value || '',
                quantity: quantity,
                unit_price: unitPrice,
                subtotal: quantity * unitPrice
            });
        }
    });
    
    return invoiceData;
}

// ✅ Función para guardar offline
async function saveInvoiceOffline(invoiceData) {
    console.log('🔴 saveInvoiceOffline called:', invoiceData);
    
    if (!window.offlineManager) {
        console.error('❌ OfflineManager no disponible');
        alert('❌ Error: Modo offline no disponible');
        return false;
    }
    
    try {
        const result = await window.offlineManager.saveInvoice(invoiceData);
        if (result.success) {
            alert('💾 Factura guardada localmente (sin internet)');
            window.location.href = '/admin/invoicing/invoice/';
            return true;
        }
        return false;
    } catch (error) {
        console.error('❌ Error guardando offline:', error);
        alert('❌ Error al guardar factura localmente');
        return false;
    }
}

// ✅ Verificar que OfflineManager existe
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(function() {
        if (window.offlineManager) {
            console.log('✅ OfflineManager disponible');
        } else {
            console.log('⚠️ OfflineManager no disponible aún, esperando...');
        }
    }, 500);
});

// ✅ Interceptar el submit del formulario de factura
function setupOfflineSubmit() {
    const form = document.querySelector('form#invoice_form, form[action*="invoicing/invoice/add/"], form[action*="invoicing/invoice/"]');
    if (form && !form._offline_listener) {
        form._offline_listener = true;
        console.log('✅ Formulario de factura detectado - configurando modo offline');
        
        form.addEventListener('submit', function(e) {
            // ✅ Si estamos offline, guardar localmente
            if (!navigator.onLine) {
                e.preventDefault();
                e.stopPropagation();
                
                console.log('🔴 Modo offline detectado - guardando factura localmente');
                
                const invoiceData = collectInvoiceData();
                console.log('📄 Datos recolectados:', invoiceData);
                
                if (invoiceData.lines.length === 0) {
                    alert('⚠️ La factura no tiene líneas. Agrega al menos un producto.');
                    return false;
                }
                
                // ✅ Guardar offline
                saveInvoiceOffline(invoiceData);
                return false;
            }
            // ✅ Si estamos online, el formulario se envía normalmente
            console.log('✅ Online - enviando factura al servidor');
        });
    }
}

// ✅ Intentar configurar el formulario cuando se carga la página
document.addEventListener('DOMContentLoaded', function() {
    setupOfflineSubmit();
});

// ✅ Observar cambios en el DOM para detectar el formulario
const observer = new MutationObserver(function(mutations) {
    setupOfflineSubmit();
});

observer.observe(document.body, {
    childList: true,
    subtree: true
});

// ============================================================
// FUNCIONES EXISTENTES
// ============================================================

// ✅ Función para obtener precio y asignarlo
function fetchProductDetails(productId, row) {
    if (!productId || productId === '') return;
    if (!row) return;
    
    console.log("🔴 Solicitando datos para producto:", productId);
    
    fetch('/admin/invoicing/get-product-price/?product_id=' + productId)
        .then(response => response.json())
        .then(data => {
            console.log("   Datos recibidos:", data);
            
            var priceInput = row.querySelector('input[name$="unit_price"]');
            if (!priceInput) {
                priceInput = row.querySelector('input[id*="unit_price"]');
            }
            
            if (priceInput) {
                priceInput.value = data.unit_price;
                priceInput.setAttribute('readonly', 'readonly');
                priceInput.style.backgroundColor = '#f0f0f0';
                priceInput.style.cursor = 'not-allowed';
                console.log("   ✅ Precio asignado (USD):", data.unit_price);
                priceInput.dispatchEvent(new Event('change', { bubbles: true }));
            }
            
            updateLineSubtotal(row);
            recalculateTotals();
        })
        .catch(error => console.error("Error:", error));
}

function updateLineSubtotal(row) {
    var qtyInput = row.querySelector('input[name$="quantity"]');
    var priceInput = row.querySelector('input[name$="unit_price"]');
    
    if (!priceInput) {
        var priceDisplay = row.querySelector('.field-unit_price');
        if (priceDisplay) {
            var text = priceDisplay.textContent || '';
            var match = text.match(/\$?\s*(\d+\.?\d*)/);
            if (match) {
                var priceValue = parseFloat(match[1]);
                console.log("   Precio extraído del texto:", priceValue);
                updateTotalsFromValues(row, qtyInput, priceValue);
                return;
            }
        }
        console.log("   ❌ No se encontraron inputs de precio");
        return;
    }
    
    if (!qtyInput) {
        console.log("   ❌ No se encontró input de cantidad");
        return;
    }
    
    var qty = parseFloat(qtyInput.value) || 0;
    var price = parseFloat(priceInput.value) || 0;
    var subtotal = qty * price;
    
    console.log("   Subtotal calculado:", qty, "x", price, "=", subtotal);
    
    var subtotalField = row.querySelector('.field-subtotal');
    if (subtotalField) {
        subtotalField.textContent = subtotal.toFixed(2);
        console.log("   ✅ Subtotal actualizado en .field-subtotal");
    }
    
    var subtotalInput = row.querySelector('input[name$="subtotal"]');
    if (subtotalInput) {
        subtotalInput.value = subtotal.toFixed(2);
        console.log("   ✅ Subtotal actualizado en input");
    }
}

function updateTotalsFromValues(row, qtyInput, priceValue) {
    var qty = parseFloat(qtyInput?.value) || 0;
    var price = priceValue || 0;
    var subtotal = qty * price;
    
    console.log("   Subtotal calculado (fallback):", qty, "x", price, "=", subtotal);
    
    var subtotalField = row.querySelector('.field-subtotal');
    if (subtotalField) {
        subtotalField.textContent = subtotal.toFixed(2);
    }
    
    var subtotalInput = row.querySelector('input[name$="subtotal"]');
    if (subtotalInput) {
        subtotalInput.value = subtotal.toFixed(2);
    }
}

// ✅ Función para recalcular todos los totales
function recalculateTotals() {
    var subtotal = 0;
    var rows = document.querySelectorAll('tr.form-row');
    
    console.log("📊 Recalculando totales, filas:", rows.length);
    
    rows.forEach(function(row) {
        var qtyInput = row.querySelector('input[name$="quantity"]');
        var priceInput = row.querySelector('input[name$="unit_price"]');
        
        var qty = parseFloat(qtyInput?.value) || 0;
        var price = 0;
        
        if (priceInput) {
            price = parseFloat(priceInput.value) || 0;
        } else {
            var priceDisplay = row.querySelector('.field-unit_price');
            if (priceDisplay) {
                var text = priceDisplay.textContent || '';
                var match = text.match(/\$?\s*(\d+\.?\d*)/);
                if (match) {
                    price = parseFloat(match[1]) || 0;
                }
            }
        }
        
        var lineTotal = qty * price;
        subtotal += lineTotal;
        console.log("   Línea: qty=", qty, "price=", price, "total=", lineTotal);
    });
    
    var taxRate = 19;
    var tax = subtotal * (taxRate / 100);
    var total = subtotal + tax;
    
    console.log("   Subtotal total USD:", subtotal, "Tax USD:", tax, "Total USD:", total);
    
    // ✅ Obtener tasa de cambio
    var rate = 0;
    var rateField = document.getElementById('id_rate_display');
    if (rateField) {
        var rateText = rateField.value || '';
        var rateMatch = rateText.match(/(\d+\.?\d*)/);
        if (rateMatch) {
            rate = parseFloat(rateMatch[1]);
        }
    }
    if (rate === 0 || isNaN(rate)) {
        rate = 40.00;
    }
    
    console.log("   💰 Tasa usada:", rate);
    
    // ✅ Actualizar campos en USD
    var subtotalField = document.getElementById('id_subtotal_display');
    var taxField = document.getElementById('id_tax_display');
    var totalField = document.getElementById('id_total_display');
    
    if (subtotalField) subtotalField.value = subtotal.toFixed(2);
    if (taxField) taxField.value = tax.toFixed(2);
    if (totalField) totalField.value = total.toFixed(2);
    
    // ✅ Actualizar campos en Bs.
    var subtotalBsField = document.getElementById('id_subtotal_bs_display');
    var taxBsField = document.getElementById('id_tax_bs_display');
    var totalBsField = document.getElementById('id_total_bs_display');
    
    if (subtotalBsField) {
        subtotalBsField.value = (subtotal * rate).toFixed(2);
        console.log("   ✅ Subtotal Bs.:", (subtotal * rate).toFixed(2));
    }
    if (taxBsField) {
        taxBsField.value = (tax * rate).toFixed(2);
        console.log("   ✅ IVA Bs.:", (tax * rate).toFixed(2));
    }
    if (totalBsField) {
        totalBsField.value = (total * rate).toFixed(2);
        console.log("   ✅ Total Bs.:", (total * rate).toFixed(2));
    }
}

// ✅ Configurar eventos en una fila
function setupRow(row) {
    console.log("🔴 Configurando fila");
    
    var select = row.querySelector('select[id$="-product"]');
    var qtyInput = row.querySelector('input[name$="quantity"]');
    var priceInput = row.querySelector('input[name$="unit_price"]');
    var rowRef = row;
    
    if (select) {
        console.log("   Select de producto encontrado");
        var $ = django.jQuery;
        
        $(select).on('select2:select', function(e) {
            var productId = e.params.data.id;
            console.log("🔴 Producto seleccionado (select2):", productId);
            if (productId) {
                this.value = productId;
                fetchProductDetails(productId, rowRef);
            }
        });
        
        select.addEventListener('change', function() {
            var productId = this.value;
            console.log("🔴 Producto seleccionado (change):", productId);
            if (productId) {
                fetchProductDetails(productId, rowRef);
            }
        });
    }
    
    if (qtyInput) {
        console.log("   Cantidad encontrada");
        qtyInput.addEventListener('change', function() {
            console.log("🔴 Cambio en cantidad:", this.value);
            updateLineSubtotal(rowRef);
            recalculateTotals();
        });
        qtyInput.addEventListener('keyup', function() {
            updateLineSubtotal(rowRef);
            recalculateTotals();
        });
    }
    
    if (priceInput) {
        priceInput.addEventListener('change', function() {
            console.log("🔴 Cambio en precio:", this.value);
            updateLineSubtotal(rowRef);
            recalculateTotals();
        });
        priceInput.addEventListener('keyup', function() {
            updateLineSubtotal(rowRef);
            recalculateTotals();
        });
    }
}

function setupAllRows() {
    console.log("🔴 Configurando todas las filas...");
    var rows = document.querySelectorAll('tr.form-row');
    console.log("   Filas encontradas:", rows.length);
    rows.forEach(function(row, index) {
        if (!row._hasSetup) {
            row._hasSetup = true;
            console.log(`   Configurando fila ${index}`);
            setupRow(row);
        }
    });
    recalculateTotals();
}

document.addEventListener('click', function(e) {
    var addButton = e.target.closest('.add-row a') || e.target.closest('.add-row');
    if (addButton) {
        console.log("🔴 Botón 'Agregar' clickeado");
        setTimeout(function() {
            var rows = document.querySelectorAll('tr.form-row');
            rows.forEach(function(row) {
                if (!row._hasSetup) {
                    row._hasSetup = true;
                    setupRow(row);
                }
            });
            recalculateTotals();
        }, 300);
        setTimeout(function() {
            recalculateTotals();
        }, 600);
    }
});

function initialize() {
    console.log("🔴 INICIALIZANDO...");
    setupAllRows();
    setupOfflineSubmit();
    console.log("✅ Inicialización completada");
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize);
} else {
    initialize();
}

setTimeout(initialize, 500);
setTimeout(initialize, 1000);
setTimeout