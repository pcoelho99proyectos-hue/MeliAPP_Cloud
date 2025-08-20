/**
 * Integración del gráfico de clases botánicas - Foco en comuna
 */

function initBotanicalChart() {
    const container = document.getElementById('botanical-chart-container');
    if (!container) {
        console.error('Error: Container #botanical-chart-container no encontrado');
        return;
    }

    const chartArea = container.querySelector('.flex-1');
    if (!chartArea) {
        console.error('Error: Chart area .flex-1 no encontrada dentro del container.');
        // No usamos innerHTML en el container para no borrar el carrusel
        return;
    }

    const userComuna = container.dataset.comuna;

    const showMessage = (message, iconClass = '', isError = false) => {
        const textColor = isError ? 'text-red-300' : 'text-slate-600';
        chartArea.innerHTML = `
            <div class="flex items-center justify-center h-full">
                <div class="text-center ${textColor}">
                    ${iconClass ? `<i class="${iconClass} text-2xl mb-2"></i>` : ''}
                    ${message}
                </div>
            </div>
        `;
    };

    if (!userComuna || userComuna === 'None' || userComuna === '') {
        showMessage('<p class="font-medium">Sin información de comuna</p><p class="text-sm text-slate-500">Actualiza tu perfil para ver el gráfico.</p>', 'fas fa-map-marker-alt');
        return;
    }

    try {
        const chart = new BotanicalChart('botanical-chart-container');
        
        // Mostrar estado de carga
        chartArea.innerHTML = `
            <div class="flex items-center justify-center h-full">
                <div class="text-center">
                    <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-400 mx-auto mb-2"></div>
                    <p class="text-white opacity-80">Cargando datos para ${userComuna}...</p>
                </div>
            </div>
        `;
        
        chart.loadData(userComuna);
        
    } catch (error) {
        console.error("Error al inicializar BotanicalChart:", error);
        showMessage(`<p class="font-medium">Error al cargar el gráfico</p><p class="text-sm">${error.message}</p>`, 'fas fa-exclamation-triangle', true);
    }
}

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', function() {
    initBotanicalChart();
});
