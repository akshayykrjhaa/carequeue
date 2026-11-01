pipeline {
    agent any

    triggers {
        pollSCM('* * * * *')
    }

    environment {
        IMAGE      = 'akki613/carequeue'
        TAG        = "${env.BUILD_NUMBER}"
        KUBECONFIG = '/var/lib/jenkins/.kube/config'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Build image') {
            steps {
                sh 'docker build -t $IMAGE:$TAG -t $IMAGE:latest .'
            }
        }

        stage('Test') {
            steps {
                sh '''
                    docker run --rm --entrypoint python $IMAGE:$TAG -c "import ast; ast.parse(open('app.py').read()); print('app.py syntax OK')"
                '''
            }
        }

        stage('Push to Docker Hub') {
            steps {
                withCredentials([usernamePassword(credentialsId: 'dockerhub-creds',
                                                  usernameVariable: 'DH_USER',
                                                  passwordVariable: 'DH_TOKEN')]) {
                    sh '''
                        echo "$DH_TOKEN" | docker login -u "$DH_USER" --password-stdin
                        docker push $IMAGE:$TAG
                        docker push $IMAGE:latest
                        docker logout
                    '''
                }
            }
        }

        stage('Deploy to Kubernetes') {
            steps {
                sh '''
                    kubectl -n carequeue rollout pause deployment/web
                    kubectl -n carequeue set image deployment/web web=$IMAGE:$TAG
                    kubectl -n carequeue set env deployment/web APP_VERSION=v1.$TAG
                    kubectl -n carequeue rollout resume deployment/web
                    kubectl -n carequeue rollout status deployment/web --timeout=180s
                '''
            }
        }

        stage('Verify') {
            steps {
                sh 'curl -sf localhost:30080/health'
            }
        }
    }

    post {
        success {
            echo "Deployed ${IMAGE}:${TAG} to Kubernetes"
        }
        failure {
            echo 'Pipeline failed. Open the red stage to see why.'
        }
    }
}
