// django_erp/static/admin/js/backup_admin.js

(function($) {
    'use strict';

    $(document).ready(function() {
        console.log("🔴 Backup admin JS cargado");
        
        // ✅ Buscar el formulario de acciones
        var actionForm = $('form').filter(function() {
            return $(this).find('select[name="action"]').length > 0;
        }).first();
        
        if (actionForm.length) {
            console.log("🔴 Formulario de acciones encontrado");
            
            // Buscar el contenedor de acciones
            var actionContainer = actionForm.find('.actions');
            
            if (actionContainer.length) {
                // Verificar si ya existe un botón "Ir"
                if (actionContainer.find('button[type="submit"]').length === 0) {
                    // Agregar botón "Ir"
                    actionContainer.append(
                        '<button type="submit" class="button" style="margin-left: 5px; padding: 5px 15px; background: #0d6efd; color: white; border: none; border-radius: 4px; cursor: pointer;">Ir</button>'
                    );
                    console.log("✅ Botón 'Ir' agregado");
                }
            }
        } else {
            console.log("❌ No se encontró formulario de acciones");
        }
    });

})(django.jQuery);  // ← Usar django.jQuery en lugar de solo $