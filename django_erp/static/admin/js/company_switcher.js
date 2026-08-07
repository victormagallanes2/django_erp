// django_erp/static/admin/js/company_switcher.js

(function() {
    'use strict';
    
    console.log('📢 company_switcher.js cargado');
    
    if (typeof Alpine === 'undefined') {
        console.warn('⚠️ Alpine NO está disponible, usando selector simple');
        return;
    }
    
    // ✅ Registrar el componente
    Alpine.data('companySwitcher', function() {
        return {
            isOpen: false,
            currentCompanyId: null,
            currentCompanyName: '',
            currentCompanyCode: '',
            availableCompanies: [],

            init: function() {
                var self = this;
                
                console.log('🏢 Inicializando companySwitcher...');
                
                try {
                    // Obtener datos de compañías desde el context processor
                    self.availableCompanies = window.COMPANIES_DATA || 
                                             {{ available_companies_json|safe|default:'[]' }};
                    
                    if (!Array.isArray(self.availableCompanies)) {
                        self.availableCompanies = [];
                    }
                    
                    self.currentCompanyId = window.CURRENT_COMPANY_ID || 
                                            {{ current_company.id|default:'null' }};
                    
                    console.log('📋 Compañías:', self.availableCompanies.length);
                    console.log('📌 ID actual:', self.currentCompanyId);
                    
                    if (self.availableCompanies.length > 0) {
                        if (self.currentCompanyId) {
                            var current = self.availableCompanies.find(function(c) {
                                return String(c.id) === String(self.currentCompanyId);
                            });
                            if (current) {
                                self.currentCompanyName = current.name;
                                self.currentCompanyCode = current.code;
                            }
                        }
                        
                        // Si no se encontró la compañía actual, usar la primera
                        if (!self.currentCompanyName && self.availableCompanies.length > 0) {
                            self.currentCompanyId = self.availableCompanies[0].id;
                            self.currentCompanyName = self.availableCompanies[0].name;
                            self.currentCompanyCode = self.availableCompanies[0].code;
                        }
                    }
                    
                    console.log('✅ Company Switcher listo:');
                    console.log('   Compañía:', self.currentCompanyCode, '-', self.currentCompanyName);
                    console.log('   Total:', self.availableCompanies.length);
                    
                } catch (e) {
                    console.error('❌ Error:', e);
                    self.availableCompanies = [];
                }
            }
        };
    });
    
    console.log('✅ Componente companySwitcher registrado en Alpine');
    
})();