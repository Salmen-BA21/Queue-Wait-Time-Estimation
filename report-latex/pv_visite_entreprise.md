# PV de Visite d'Entreprise  
## Projet de Fin d'Études

**Auteur :** Salmen Ben Ammar  
**Date :** 16 avril 2026

## Introduction
Cette visite d'entreprise s'inscrit dans le cadre de mon Projet de Fin d'Études (PFE) portant sur le développement d'un système d'estimation des temps d'attente en file d'attente utilisant la vision par ordinateur. Le projet vise à analyser les files d'attente dans les environnements commerciaux en temps réel, en intégrant des technologies telles que YOLO pour la détection d'objets, ByteTrack pour le suivi, et des workflows n8n pour l'automatisation des alertes.

Durant les derniers mois, j'ai travaillé sur la mise en place des composants principaux du système. Dans ce rapport, je présente un résumé des activités réalisées et les tâches restantes pour finaliser le projet.

## Activités Réalisées
### Mise en Place de l'Infrastructure
- Configuration de l'environnement de développement avec Python, FastAPI pour le backend, et React pour l'interface utilisateur.
- Intégration de modèles YOLO (YOLOv8) pour la détection des personnes en file d'attente.
- Implémentation du suivi des objets avec ByteTrack pour maintenir la continuité des trajectoires.

### Développement du Backend
- Création d'un serveur FastAPI pour traiter les flux vidéo en temps réel.
- Calcul des métriques de file d'attente : taux d'arrivée , taux de service, temps d'attente estimé  basé sur la théorie des files d'attente M/M/1.
- Intégration d'une estimation d'incertitude utilisant des distributions Gamma pour les paramètres.

### Workflows d'Automatisation
- Conception et déploiement de workflows n8n pour la gestion des alertes (par exemple, alertes Telegram en cas de dépassement des seuils de temps d'attente).
- Configuration des webhooks pour l'envoi automatique des métriques depuis le backend vers n8n.

### Interface Utilisateur et Tests
- Développement d'une interface web avec React pour visualiser les métriques en temps réel.
- Mise en place de tests unitaires et d'intégration pour valider les composants.

## État Actuel du Projet
À ce jour, le système est capable de traiter des flux vidéo en temps réel, de calculer les métriques de file d'attente, et d'envoyer des alertes automatiques via Telegram. Les tests montrent une précision acceptable pour la détection et le suivi, avec une gestion des incertitudes pour améliorer la fiabilité des estimations.

Cependant, des optimisations sont encore nécessaires pour réduire la latence et améliorer la robustesse en environnements variables (éclairage, occlusions).

## Travaux Restants
### Optimisations et Améliorations
- Optimisation des performances : réduction de la latence du traitement vidéo et amélioration de l'efficacité des modèles YOLO.
- Amélioration de la gestion des incertitudes : raffinement des méthodes d'estimation bayésienne pour une meilleure précision.

### Déploiement et Validation
- Déploiement en production avec Docker et configuration des caméras IP.
- Tests en conditions réelles dans un environnement commercial pour valider les performances.
- Documentation complète et préparation du rapport final de PFE.

### Fonctionnalités Supplémentaires
- Intégration de WebRTC pour la prévisualisation en temps réel des flux vidéo.
- Extension des workflows n8n pour inclure d'autres canaux d'alerte (email, SMS).

## Conclusion
Ce PFE m'a permis d'acquérir une expérience pratique dans le domaine de la vision par ordinateur appliquée aux systèmes intelligents. Les mois passés ont été consacrés à la construction des fondations du système, et les tâches restantes se concentrent sur les optimisations et la validation finale. Je prévois de finaliser le projet d'ici la fin du semestre, en m'assurant que toutes les exigences sont satisfaites.