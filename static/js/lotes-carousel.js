let selectedLote = { id: null, nombre: null };

document.addEventListener('DOMContentLoaded', () => {
    const carouselContainer = document.getElementById('lotes-carousel-container');
    if (!carouselContainer) {
        console.error('Error: Carousel container #lotes-carousel-container not found.');
        return;
    }

    const userId = carouselContainer.dataset.userId;
    if (!userId || userId === 'None') {
        return;
    }

    loadLotes(userId);

    // Event listeners for QR buttons
    const generateBtn = document.getElementById('lote-generate-qr-btn');
    const downloadBtn = document.getElementById('lote-download-qr-btn');

    if (generateBtn) {
        generateBtn.addEventListener('click', () => {
            if (selectedLote.id) {
                generateLoteQR(selectedLote.id, true);
            }
        });
    }

    if (downloadBtn) {
        downloadBtn.addEventListener('click', () => {
            if (selectedLote.id && selectedLote.nombre) {
                downloadLoteQR(selectedLote.id, selectedLote.nombre);
            }
        });
    }
});

async function loadLotes(userId) {
    const carousel = document.getElementById('lotes-carousel');
    if (!carousel) return;

    try {
        const response = await fetch(`/api/lotes/${userId}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        const lotes = data.success ? data.lotes : (Array.isArray(data) ? data : []);
        renderLotesCarousel(lotes);
    } catch (error) {
        console.error('Error loading lotes:', error);
        carousel.innerHTML = `<p class="text-red-500 col-span-full">Error al cargar lotes.</p>`;
    }
}

function renderLotesCarousel(lotes) {
    const carousel = document.getElementById('lotes-carousel');
    if (!carousel) return;

    carousel.innerHTML = '';

    if (!lotes || lotes.length === 0) {
        carousel.innerHTML = '<p class="text-gray-500 col-span-full">Este usuario no tiene lotes registrados.</p>';
        return;
    }

    lotes.forEach(lote => {
        const loteButton = document.createElement('button');
        loteButton.dataset.loteId = lote.id;
        loteButton.className = 'flex-shrink-0 w-20 h-14 bg-gradient-to-br from-white via-amber-50/70 to-yellow-100/50 dark:from-yellow-600 dark:via-amber-800/70 dark:to-yellow-1000 rounded-lg shadow-md p-1 flex flex-col items-center justify-center text-center hover:shadow-lg hover:from-yellow-50 hover:to-amber-100 dark:hover:from-slate-500 dark:hover:to-amber-700/30 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-yellow-500 border border-amber-200/40 dark:border-amber-600/30';
        loteButton.type = 'button';

        loteButton.innerHTML = `
            <span class="text-lg font-bold text-yellow-500">${lote.orden_miel}</span>
            <span class="text-xs font-semibold text-gray-700 break-words overflow-hidden text-ellipsis">${lote.nombre_miel}</span>
        `;

        loteButton.addEventListener('click', handleLoteButtonClick);
        carousel.appendChild(loteButton);
    });
    
    // Scroll to the first element after rendering
    setTimeout(() => {
        if (carousel.firstElementChild) {
            carousel.scrollLeft = 0;
            carousel.firstElementChild.scrollIntoView({ behavior: 'smooth', inline: 'start' });
        }
    }, 100);
}

async function handleLoteButtonClick(event) {
    const button = event.currentTarget;
    const loteId = button.dataset.loteId;
    const loteNombre = button.querySelector('.text-xs').textContent;
    const loteOrden = button.querySelector('.text-lg').textContent;

    if (!loteId) {
        console.error('No lote ID found on the button.');
        return;
    }

    console.log(`Button clicked for lote: ${loteNombre} (ID: ${loteId})`);

    try {
        // Generate URL and make request to backend
        const url = `/api/lote/click/${loteId}`;
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                lote_id: loteId,
                lote_nombre: loteNombre,
                lote_orden: loteOrden,
                timestamp: new Date().toISOString()
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (data.success) {
            // Show HTML success message
            showSuccessMessage(data);
            
            // The call to showQRCarousel() was removed to fix an error.

            // Update selected lote state
            selectedLote.id = loteId;
            selectedLote.nombre = loteNombre;

            // Generate and display the QR code for the selected lot
            generateLoteQR(loteId, false); // Don't force regenerate on first click
            
            // Also fetch and update composition if available
            fetchAndUpdateComposition(loteId);
            
        } else {
            console.error(`Error processing click: ${data.error}`);
            showErrorMessage(`Error: ${data.error}`);
        }
    } catch (error) {
        console.error('Failed to process lote click:', error);
        showErrorMessage(`Error de conexión: ${error.message}`);
    }
}

function showSuccessMessage(data) {
    // Create success message HTML
    const messageHtml = `
        <div class="fixed top-4 right-4 bg-green-500 text-white px-6 py-4 rounded-lg shadow-lg z-50 max-w-md">
            <div class="flex items-start">
                <div class="flex-shrink-0">
                    <svg class="h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                </div>
                <div class="ml-3">
                    <h3 class="text-sm font-medium">¡Lote Seleccionado!</h3>
                    <div class="mt-2 text-sm">
                        <p><strong>Lote:</strong> ${data.lote_nombre}</p>
                        <p><strong>Orden:</strong> ${data.lote_orden}</p>
                    </div>
                </div>
                <button onclick="this.parentElement.parentElement.remove()" class="ml-4 text-white hover:text-gray-200">
                    <span class="sr-only">Cerrar</span>
                    <svg class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                        <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
                    </svg>
                </button>
            </div>
        </div>
    `;
    
    // Add message to page
    document.body.insertAdjacentHTML('beforeend', messageHtml);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        const message = document.querySelector('.fixed.top-4.right-4.bg-green-500');
        if (message) message.remove();
    }, 5000);
}

function showErrorMessage(errorText) {
    const messageHtml = `
        <div class="fixed top-4 right-4 bg-red-500 text-white px-6 py-4 rounded-lg shadow-lg z-50 max-w-md">
            <div class="flex items-start">
                <div class="flex-shrink-0">
                    <svg class="h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                </div>
                <div class="ml-3">
                    <h3 class="text-sm font-medium">Error</h3>
                    <p class="mt-1 text-sm">${errorText}</p>
                </div>
                <button onclick="this.parentElement.parentElement.remove()" class="ml-4 text-white hover:text-gray-200">
                    <span class="sr-only">Cerrar</span>
                    <svg class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                        <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
                    </svg>
                </button>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', messageHtml);
    
    setTimeout(() => {
        const message = document.querySelector('.fixed.top-4.right-4.bg-red-500');
        if (message) message.remove();
    }, 5000);
}

async function fetchAndUpdateComposition(loteId) {
    try {
        const response = await fetch(`/api/lote/composicion/${loteId}`);
        if (!response.ok) return;
        
        const data = await response.json();
        if (data.success) {
            const compositionData = parseCompositionData(data.composicion);
            updateBotanicalChartWithComposition(compositionData);
        }
    } catch (error) {
        console.log('Could not fetch composition data:', error);
    }
}

function parseCompositionData(compositionString) {
    // Parse "Trebol Blanco:100" format
    const compositions = {};
    if (!compositionString) return compositions;
    
    const entries = compositionString.split(',');
    entries.forEach(entry => {
        const [species, percentage] = entry.split(':');
        if (species && percentage) {
            compositions[species.trim()] = parseFloat(percentage.trim());
        }
    });
    
    return compositions;
}

function updateBotanicalChartWithComposition(compositionData) {
    // Find botanical chart instance and update it with composition data
    if (window.BotanicalChart && window.botanicalChartInstance) {
        window.botanicalChartInstance.updateWithComposition(compositionData);
    } else {
        console.warn('Botanical chart not found or not initialized');
    }
}

function generateLoteQR(loteId, force = false) {
    const qrSection = document.getElementById('lote-qr-section');
    const qrImage = document.getElementById('lote-qr-image');
    const qrPlaceholder = document.getElementById('lote-qr-placeholder');
    const qrNombre = document.getElementById('lote-qr-nombre');
    const generateBtn = document.getElementById('lote-generate-qr-btn');
    const downloadBtn = document.getElementById('lote-download-qr-btn');

    if (!qrSection || !qrImage || !qrPlaceholder || !qrNombre) return;

    // Show the section
    qrSection.style.display = 'block';
    qrNombre.textContent = `Lote: ${selectedLote.nombre}`;

    // Generate QR URL
    let qrApiUrl = `/api/lote/${loteId}/qr`;
    if (force) {
        qrApiUrl += `?t=${new Date().getTime()}`; // Cache buster
    }

    qrImage.src = qrApiUrl;
    qrImage.style.display = 'block';
    qrPlaceholder.style.display = 'none';

    // Enable buttons
    generateBtn.disabled = false;
    downloadBtn.disabled = false;

    if (force) {
        showNotification('Nuevo QR generado.', 'success');
    }
}

function downloadLoteQR(loteId, loteNombre) {
    const link = document.createElement('a');
    link.href = `/api/lote/${loteId}/qr`;
    link.download = `qr-lote-${loteNombre.replace(/\s+/g, '_')}.png`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    showNotification('Descarga del QR iniciada.', 'success');
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `fixed top-4 right-4 px-6 py-3 rounded-lg shadow-lg z-50 ${
        type === 'success' ? 'bg-green-500 text-white' :
        type === 'error' ? 'bg-red-500 text-white' :
        'bg-blue-500 text-white'
    }`;
    notification.textContent = message;
    document.body.appendChild(notification);
    setTimeout(() => {
        notification.remove();
    }, 3000);
}
