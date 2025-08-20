/**
 * Componente de gráfico de clases botánicas por comuna
 */

class BotanicalChart {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.comuna = null;
        this.data = null;
    }

    async loadData(comuna) {
        console.log('🌿 BotanicalChart.loadData() called with:', comuna);
        
        if (!comuna) {
            console.log('❌ Comuna no especificada');
            this.showMessage('Comuna no especificada');
            return;
        }

        this.comuna = comuna;
        
        try {
            console.log('📡 Fetching data from:', `/api/botanical-classes/${encodeURIComponent(comuna)}`);
            const response = await fetch(`/api/botanical-classes/${encodeURIComponent(comuna)}`);
            const data = await response.json();
            
            console.log('📊 API Response:', data);
            
            if (data.success) {
                console.log('✅ Data loaded successfully:', data.classes.length, 'items');
                this.data = data.classes;
                this.render();
            } else {
                console.log('⚠️ API returned error:', data.message);
                this.showMessage(data.message || 'Comuna no registrada');
            }
        } catch (error) {
            console.error('❌ Error loading botanical data:', error);
            this.showMessage('Error al cargar datos');
        }
    }

    render() {
        console.log('🎨 BotanicalChart.render() called');
        console.log('📊 Data to render:', this.data);
        
        if (!this.data || this.data.length === 0) {
            console.log('⚠️ No data to render');
            this.showMessage('No hay datos disponibles para esta comuna');
            return;
        }

        console.log('🖼️ Rendering chart with', this.data.length, 'items');

        let html = `
            <div class="botanical-chart bg-white rounded-lg shadow-md p-4">
                <div class="space-y-3">
        `;

        if (this.data && this.data.length > 0) {
            // Ordenar por categoría para mejor organización pedagógica
            const sortedData = [...this.data].sort((a, b) => {
                const order = {'Leñosa': 1, 'Leñosa Mixta': 2, 'Herbácea': 3, 'Mixta': 4};
                return (order[a.categoria] || 5) - (order[b.categoria] || 5);
            });

            // Tarjetas con nombres completos sin truncar
            const classesHtml = sortedData.map(cls => `
                <div class="botanical-full-card rounded-lg p-3" style="border-left: 3px solid ${cls.color}; background: ${cls.color}08;">
                    <!-- Header con título completo -->
                    <div class="class-full-header flex items-center gap-2 mb-2">
                        <span class="text-xl" style="color: ${cls.color};">${cls.icono}</span>
                        <div class="flex-1">
                            <h4 class="font-bold text-sm" style="color: ${cls.color};">${cls.titulo}</h4>
                            <p class="text-xs text-gray-600">${cls.cantidad} especies</p>
                        </div>
                    </div>

                    <!-- Lista completa de especies sin truncar -->
                    <div class="species-full-list space-y-1">
                        ${cls.especies.map(specie => 
                            `<span class="species-full-item block text-xs py-0.5 px-1 rounded-sm" style="background-color: ${cls.color}10; color: ${cls.color};">${specie}</span>`
                        ).join('')}
                    </div>
                </div>
            `).join('');
            
            html += `
                <div class="botanical-chart-header mb-4">
                    <h3 class="text-xl font-bold text-gray-800 mb-2">
                        🌿 Clases Botánicas en ${this.comuna}
                    </h3>
                    <p class="text-sm text-gray-600">
                        ${this.data.length} categoría${this.data.length !== 1 ? 's' : ''} identificadas
                    </p>
                </div>
                
                <!-- Grid responsivo 2-3 columnas -->
                <div class="botanical-grid grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                    ${classesHtml}
                </div>
            `;
        }

        console.log('🎯 Final HTML to be rendered:', html);
        
        // Buscar el área específica del gráfico para preservar el carrusel
        const chartArea = this.container.querySelector('.flex-1');
        if (chartArea) {
            // Solo reemplazar el área del gráfico, preservando el carrusel
            chartArea.innerHTML = html;
        } else {
            // Fallback: reemplazar todo el contenido
            this.container.innerHTML = html;
        }
    }

    showMessage(message) {
        const messageHtml = `
            <div class="bg-yellow-50 border-l-4 border-yellow-400 p-4 rounded-md">
                <div class="flex">
                    <div class="flex-shrink-0">
                        <svg class="h-5 w-5 text-yellow-400" viewBox="0 0 20 20" fill="currentColor">
                            <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
                        </svg>
                    </div>
                    <div class="ml-3">
                        <p class="text-sm text-yellow-700">${message}</p>
                    </div>
                </div>
            </div>
        `;
        
        // Buscar el área específica del gráfico para preservar el carrusel
        const chartArea = this.container.querySelector('.flex-1');
        if (chartArea) {
            chartArea.innerHTML = messageHtml;
        } else {
            this.container.innerHTML = messageHtml;
        }
    }

    // Método para actualizar automáticamente cuando cambia la comuna
    updateCommune(newCommune) {
        this.loadData(newCommune);
    }
}

// Función auxiliar para inicializar el gráfico
function initBotanicalChart(containerId) {
    return new BotanicalChart(containerId);
}

// Exportar para uso global
window.BotanicalChart = BotanicalChart;
window.initBotanicalChart = initBotanicalChart;
