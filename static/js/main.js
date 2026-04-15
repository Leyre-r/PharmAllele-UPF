window.addEventListener('DOMContentLoaded', event => {

    // 1. Inicializar la tabla 
    const table = $('#table-output').DataTable({
        language: { url: 'https://cdn.datatables.net/plug-ins/1.13.1/i18n/es-ES.json' }
    });

    // 2. Localizar el formulario
    const searchForm = document.querySelector('.search-panel');

    if (searchForm) {
        searchForm.addEventListener('submit', function (e) {
            // Evitar que la página se recargue 
            e.preventDefault(); 

            // Recoger lo que el usuario escribió
            const drug = document.querySelector('input[name="drug"]').value;
            const variant = document.querySelector('input[name="variant"]').value;

            console.log("Pidiendo datos a Flask para:", drug, variant);

            // 3. Llamada a app.py
            // Usamos format=json para que el Python sepa que somos nosotros (el JS)
            fetch(`/search?drug=${drug}&variant=${variant}&format=json`)
                .then(response => response.json())
                .then(data => {
                    console.log("Datos recibidos:", data);
                    
                    table.clear();
                    data.forEach(item => {
                        table.row.add([
                            item.drugs_drug_name,
                            item.variants_variant_name,
                            item.phenotype_category_phenotype_category,
                            item.illness_illness_name,
                            item.evidence_category_evidence_category
                        ]);
                    });
                    table.draw();

                    const trace = {
                        x: data.map(i => i.drugs_drug_name),
                        y: data.map(i => i.variants_variant_name.length), // Un ejemplo visual
                        type: 'bar',
                        marker: {color: '#1abc9c'}
                    };
                    Plotly.newPlot('myDiv', [trace], {title: 'Resultados por Fármaco'});
                })
                .catch(error => console.error("Error en la búsqueda:", error));
        });
    }
});
    // --- 3. FUNCIÓN FETCH  ---
    function ejecutarBusqueda(g, v, d) {
        
        const datosPrueba = [
            {gene: g || "CYP2D6", variant: v || "∗4", drug: d || "Tamoxifen", significance: "High"},
            {gene: g || "VKORC1", variant: v || "rs9923231", drug: d || "Warfarin", significance: "Medium"}
        ];

        actualizarPantalla(datosPrueba);
    }

    // --- 4. ACTUALIZAR TABLA Y GRÁFICO ---
    function actualizarPantalla(datos) {
        // Actualizar Tabla
        table.clear();
        datos.forEach(item => {
            table.row.add([item.gene, item.variant, item.drug, item.significance]);
        });
        table.draw();

        const traces = [{
            x: datos.map(d => d.drug),
            y: [10, 20], // Aquí pondrías valores reales de tu DB
            type: 'bar',
            marker: { color: '#1abc9c' }
        }];

        Plotly.newPlot('myDiv', traces, { title: 'Resultados de Farmacogenética' });
        
        alert("¡Datos actualizados!");
    }

    // --- 5. LÓGICA DEL TEMPLATE  ---
    // Esto hace que el menú cambie al hacer scroll
    var navbarShrink = function () {
        const navbarCollapsible = document.body.querySelector('#mainNav');
        if (!navbarCollapsible) return;
        if (window.scrollY === 0) {
            navbarCollapsible.classList.remove('navbar-shrink')
        } else {
            navbarCollapsible.classList.add('navbar-shrink')
        }
    };
    navbarShrink();
    document.addEventListener('scroll', navbarShrink);

});
