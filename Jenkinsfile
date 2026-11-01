pipeline {
    agent any

    triggers {
        pollSCM('* * * * *')
    }

    environment {
        IMAGE      = 'akki613/carequeue'
        TAG        = "${env.BUILD_NUMBER}"
        KUBECONFIG = '/var/lib/jenkins/.kube/config'
        NS         = 'carequeue'
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

        stage('Find live colour') {
            steps {
                script {
                    env.LIVE = sh(script: 'kubectl -n $NS get service web -o jsonpath="{.spec.selector.track}"', returnStdout: true).trim()
                    env.IDLE = (env.LIVE == 'blue') ? 'green' : 'blue'
                }
                echo "Live colour: ${env.LIVE}. The new version will go to: ${env.IDLE}"
            }
        }

        stage('Deploy to idle colour') {
            steps {
                sh '''
                    kubectl -n $NS rollout pause deployment/web-$IDLE
                    kubectl -n $NS set image deployment/web-$IDLE web=$IMAGE:$TAG
                    kubectl -n $NS set env deployment/web-$IDLE APP_VERSION=v2.$TAG
                    kubectl -n $NS rollout resume deployment/web-$IDLE
                    kubectl -n $NS scale deployment/web-$IDLE --replicas=3
                    kubectl -n $NS rollout status deployment/web-$IDLE --timeout=180s
                    kubectl -n $NS set selector service web-preview app=web,track=$IDLE
                '''
            }
        }

        stage('Smoke test on preview') {
            steps {
                sh '''
                    for i in 1 2 3 4 5 6; do
                        if curl -sf localhost:30081/health | grep -q "v2.$TAG"; then
                            echo "Preview is healthy and running v2.$TAG:"
                            curl -s localhost:30081/health
                            exit 0
                        fi
                        sleep 5
                    done
                    echo "Preview did not report v2.$TAG"
                    exit 1
                '''
            }
        }

        stage('Approve switch') {
            steps {
                timeout(time: 15, unit: 'MINUTES') {
                    input message: "Version v2.${env.TAG} is running on ${env.IDLE} (preview on port 30081). Switch live traffic from ${env.LIVE} to ${env.IDLE}?",
                          ok: "Switch to ${env.IDLE}"
                }
            }
        }

        stage('Switch live traffic') {
            steps {
                sh 'kubectl -n $NS set selector service web app=web,track=$IDLE'
            }
        }

        stage('Verify live') {
            steps {
                sh '''
                    for i in 1 2 3 4 5 6; do
                        if curl -sf localhost:30080/health | grep -q "v2.$TAG"; then
                            echo "Live site is serving v2.$TAG:"
                            curl -s localhost:30080/health
                            exit 0
                        fi
                        sleep 5
                    done
                    echo "Live site did not report v2.$TAG"
                    exit 1
                '''
            }
        }

        stage('Point preview at old colour') {
            steps {
                sh 'kubectl -n $NS set selector service web-preview app=web,track=$LIVE'
            }
        }
    }

    post {
        success {
            echo "Live traffic is now on ${env.IDLE} (${IMAGE}:${TAG}). ${env.LIVE} is still running for instant rollback."
        }
        aborted {
            echo "Switch not approved. Users stay on ${env.LIVE}. ${env.IDLE} keeps the new version for more testing."
        }
        failure {
            echo 'Pipeline failed. Open the red stage to see why.'
        }
    }
}
