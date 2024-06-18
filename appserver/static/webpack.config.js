const path = require("path");
const HtmlWebPackPlugin = require("html-webpack-plugin");

const htmlPlugin = new HtmlWebPackPlugin({
    template: "./src/index.html",
});

module.exports = {
    entry: "./src/index.tsx",
    module: {
        rules: [
            {
                test: /\.tsx?$/,
                use: "ts-loader",
                exclude: /node_modules/,
            },
            {
                test: /\.css$/,
                use: [
                    'style-loader',
                    'css-loader',
                ],
            },
        ],
    },

    resolve: {
        extensions: [".tsx", ".ts", ".js"],
        fallback: {
            fs: false,
            tls: false,
            net: false,
            path: false,
            zlib: false,
            http: false,
            https: false,
            stream: false,
            crypto: false,
            buffer: false,
            util: false,
            os: false,
            url: false,
        }
    },

    output: {
        filename: "bundle.js",
        path: path.resolve(__dirname, "dist"),
    },

    plugins: [htmlPlugin],
    devServer: {
        static: {directory: path.join(__dirname, 'dist')},
        compress: true,
        port: 9000
    }
};