let config = {
        cors: "allowAll",
        address: "0.0.0.0",
        port: 8080,
        basePath: "/",
        ipWhitelist: [],
        useHttps: false,
        httpsPrivateKey: "",
        httpsCertificate: "",
        language: "fr",
        locale: "fr-CH",
        logLevel: ["INFO", "LOG", "WARN", "ERROR"],
        timeFormat: 24,
        units: "metric",

        modules: [
                {
                        module: "alert",
                },
                {
                        module: "clock",
                        position: "top_left",
                        config: {
                                displaySeconds: false,
                                showDate: true,
                        }
                },
                {
                        module: "calendar",
                        header: "Prochains jours fériés",
                        position: "top_left",
                        config: {
                                colored: true,
                                maximumEntries: 4,
                                maximumNumberOfDays: 365,
                                fetchInterval: 24 * 60 * 60 * 1000,
                                calendars: [
                                        {
                                                symbol: "church",
                                                color: "#e74c3c",
                                                url: "http://localhost:8090/valais.ics"
                                        }
                                ]
                        }
                },
                {
                        module: "weather",
                        header: "Météo — Maintenant",
                        position: "top_right",
                        classes: "weather-current",
                        config: {
                                weatherProvider: "openmeteo",
                                type: "current",
                                lat: 46.2512,
                                lon: 7.3492,
                                showWindDirection: false,
                                showWindDirectionAsArrow: false,
                                showHumidity: true,
                        }
                },
                {
                        module: "weather",
                        header: "Prévision — 2 jours",
                        position: "top_right",
                        classes: "weather-forecast",
                        config: {
                                weatherProvider: "openmeteo",
                                type: "forecast",
                                lat: 46.2512,
                                lon: 7.3492,
				maxNumberOfDays: 3,
                                showWindDirection: false,
                                colored: true,
                        }
                },
                {
                        module: "newsfeed",
                        position: "bottom_bar",
                        classes: "page-news",
                        config: {
                                feeds: [
                                        {
                                                title: "Suisse",
                                                url: "https://news.google.com/rss?hl=fr&gl=CH&ceid=CH:fr"
                                        }
                                ],
                                showSourceTitle: true,
                                showPublishDate: false,
                                broadcastNewsFeeds: true,
                                broadcastNewsUpdates: true,
                                updateInterval: 15000,
                        }
                },
                {
                        module: "MMM-pages",
                        config: {
                                modules: [
                                        ["clock", "calendar", "weather-current", "weather-forecast", "page-news"],
                                        ["page-stocks"],
                                        ["page-mqtt"],
                                        ["page-newsapi"],
                                        ["page-timer"],
                                ],
                                fixed: ["MMM-page-indicator"],
                                timings: { default: 30000 },
                                animationTime: 1000,
                        }
                },
                {
                        module: "MMM-MQTT",
                        position: "bottom_left",
                        header: "Balcon — Savièse 870m",
                        classes: "page-mqtt",
                        config: {
                                logging: false,
                                mqttServers: [
                                        {
                                                address: "mqtt3.thingspeak.com",
                                                port: "1883",
                                                clientId: "000000000000000000000000",
                                                user: "000000000000000000000000",
                                                password: "000000000000000000000000+0ZJrrdXno",
                                                subscriptions: [
                                                        {
                                                                topic: "channels/2554355/subscribe",
                                                                label: "Température",
                                                                suffix: " °C",
                                                                decimals: 1,
                                                                jsonpointer: "/field1",
                                                                sortOrder: 10,
                                                                maxAgeSeconds: 700,
                                                                colors: [
                                                                        { upTo: 0,  value: "#00ccff" },
                                                                        { upTo: 10, value: "#aaddff" },
                                                                        { upTo: 20, value: "green"   },
                                                                        { upTo: 30, value: "orange"  },
                                                                        { upTo: 50, value: "red"     },
                                                                ],
                                                        },
                                                        {
                                                                topic: "channels/2554355/subscribe",
                                                                label: "Humidité",
                                                                suffix: " %",
                                                                decimals: 1,
                                                                jsonpointer: "/field2",
                                                                sortOrder: 20,
                                                                maxAgeSeconds: 700,
                                                        },
                                                        {
                                                                topic: "channels/2554355/subscribe",
                                                                label: "CO₂",
                                                                suffix: " ppm",
                                                                decimals: 0,
                                                                jsonpointer: "/field3",
                                                                sortOrder: 30,
                                                                maxAgeSeconds: 700,
                                                                colors: [
                                                                        { upTo: 800,  value: "green"  },
                                                                        { upTo: 1200, value: "orange" },
                                                                        { upTo: 5000, value: "red"    },
                                                                ],
                                                        },
                                                        {
                                                                topic: "channels/2554355/subscribe",
                                                                label: "QNH mer",
                                                                suffix: " hPa",
                                                                decimals: 2,
                                                                jsonpointer: "/field4",
                                                                sortOrder: 40,
                                                                maxAgeSeconds: 700,
                                                        },
                                                        {
                                                                topic: "channels/2554355/subscribe",
                                                                label: "Pression locale",
                                                                suffix: " hPa",
                                                                decimals: 2,
                                                                jsonpointer: "/field5",
                                                                sortOrder: 50,
                                                                maxAgeSeconds: 700,
                                                        },
                                                        {
                                                                topic: "channels/2554355/subscribe",
                                                                label: "Tendance 3h",
                                                                suffix: " hPa",
                                                                decimals: 2,
                                                                jsonpointer: "/field6",
                                                                sortOrder: 60,
                                                                maxAgeSeconds: 700,
                                                                colors: [
                                                                        { upTo: -1,  value: "#00ccff" },
                                                                        { upTo: 0,   value: "gray"    },
                                                                        { upTo: 1,   value: "green"   },
                                                                        { upTo: 999, value: "orange"  },
                                                                ],
                                                        },
                                                ]
                                        }
                                ],
                        }
                },
                {
                        module: "MMM-AVStock",
                        position: "bottom_bar",
                        classes: "page-stocks",
                        config: {
                                symbols: ["^SSMI", "BZ=F", "^NDX", "^GSPC", "^GDAXI", "^N225", "000001.SS", "^HSI"],
                                alias: ["SMI", "Brent", "Nasdaq 100", "S&P 500", "DAX 40", "Nikkei", "Shanghai", "Hang Seng"],
                                mode: "table",
                                showChart: false,
                        }
                },
                                {
                        module: "MMM-NewsAPI",
                        header: "USA — Actualités",
                        position: "top_left",
                        classes: "page-newsapi",
                        config: {
                                apiKey: "000000000000000000000000",
                                type: "horizontal",
                                choice: "headlines",
                                pageSize: 10,
                                drawInterval: 1000 * 20,
                                templateFile: "template.html",
                                fetchInterval: 1000 * 60 * 60,
                                query: {
                                        country: "us",
                                }
                        }
                },
                {
                        module: "MMM-NewsAPI",
                        header: "France — Actualités",
                        position: "lower_third",
                        classes: "page-newsapi",
                        config: {
                                apiKey: "000000000000000000000000",
                                type: "horizontal",
                                choice: "everything",
                                pageSize: 10,
                                drawInterval: 1000 * 20,
                                templateFile: "template.html",
                                fetchInterval: 1000 * 60 * 60,
                                query: {
                                        language: "fr",
                                        domains: "lemonde.fr,lefigaro.fr,liberation.fr,leparisien.fr",
                                        sortBy: "publishedAt",
                                }
                        }
                },
                {
                        module: "MMM-Timer",
                        position: "fullscreen_above",
                        classes: "page-timer",
                        config: {
                                defaultHours: 0,
                                defaultMinutes: 15,
                                defaultSeconds: 0,

                                // Affichage
                                showControls: true,
                                timerFontSize: "8rem",

                                // Alerte de fin
                                flashColor: "#ff0000",
                                flashInterval: 500,

                                // Gestion des pages MMM-pages (index 0-based : page 5 = index 4)
                                lockPageOnStart: true,
                                targetPage: 4,
                                restoreNavigationOnStop: true,

                                // Comportement après arrêt
                                autoResetAfterStop: true,
                        }
                },
                {
                        module: "MMM-page-indicator",
                        position: "bottom_bar",
                        config: {
                                pages: 5,
                                activeBright: true,
                                inactiveDimmed: true,
                                inactiveHollow: true,
                        }
                },
        ]
};

/*************** DO NOT EDIT THE LINE BELOW ***************/
if (typeof module !== "undefined") { module.exports = config; }
