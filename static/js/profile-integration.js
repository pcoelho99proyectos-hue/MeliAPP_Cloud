/**
 * Integración del gráfico de clases botánicas - Foco en comuna
 */

function initBotanicalChart() {
    const container = document.getElementById('botanical-chart-container');
    
    if (!container) {
        container.innerHTML = '<div class="text-red-500">Error: Container no encontrado</div>';
        return;
    }
    
    // Obtener comuna del usuario
    const userComuna = container.dataset.comuna;
    
    // Mostrar debugging visible dentro del contenedor
    container.innerHTML = `
        <div class="p-4 text-sm">
            <div class="bg-blue-50 border border-blue-200 rounded p-3 mb-2">
                <strong>Debug:</strong> Comuna detectada = <span class="font-mono">${userComuna}</span>
            </div>
            <div class="bg-green-50 border border-green-200 rounded p-3">
                <strong>Estado:</strong> Inicializando gráfico...
            </div>
        </div>
    `;
    
    if (!userComuna || userComuna === 'None' || userComuna === '') {
        container.innerHTML = `
            <div class="flex items-center justify-center h-full">
                <div class="text-center text-slate-600">
                    <i class="fas fa-map-marker-alt text-2xl mb-2"></i>
                    <p class="font-medium">Sin información de comuna</p>
                    <p class="text-sm text-slate-500">Comuna: ${userComuna || 'vacía'}</p>
                </div>
            </div>
        `;
        return;
    }
    
    // Inicializar gráfico con la comuna detectada
    try {
        const chart = new BotanicalChart('botanical-chart-container');
        
        // Mostrar estado de carga
        container.innerHTML = `
            <div class="flex items-center justify-center h-full">
                <div class="text-center">
                    <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-400 mx-auto mb-2"></div>
                    <p class="text-slate-600">Cargando datos botánicos para ${userComuna}...</p>
                </div>
            </div>
        `;
        
        chart.loadData(userComuna);
        
    } catch (error) {
        container.innerHTML = `
            <div class="bg-red-50 border border-red-200 rounded p-4">
                <div class="text-red-600">
                    <strong>Error al cargar gráfico:</strong><br>
                    ${error.message}
                </div>
            </div>
        `;
    }
}

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', function() {
    initBotanicalChart();
});
